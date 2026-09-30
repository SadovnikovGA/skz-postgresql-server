import copy,os,sys,unittest
from contextlib import contextmanager
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
os.environ.setdefault('DATABASE_URL','postgresql://skz:test@127.0.0.1:5432/skz')
os.environ.setdefault('SESSION_SECRET','test-only-session-secret-01234567890123456789')
from domain import *
import app as web

def record(**kw):
    r={k:None for k in COLUMNS}
    r.update(id=1,source_date='31.07.2026',title='Заявка',request_id='001',registered_at=datetime(2026,7,31,17),export_time='09-00',citizen_id='0001',district='ЦАО',area='Тверской',uploaded_by=2,revision=1,archived_at=None)
    r.update(kw);return calculate(r,set())

class BusinessTests(unittest.TestCase):
    def test_exact_boundary_weekends_and_holiday(self):
        for dt,due in [('31.07.2026 17:00:00','2026-08-03'),('31.07.2026 17:00:01','2026-08-04'),('01.08.2026 10:00:00','2026-08-04'),('02.08.2026 10:00:00','2026-08-04')]:
            with self.subTest(dt=dt):self.assertEqual(calculate(record(registered_at=parse_datetime(dt)),set())['fd_due_date'].isoformat(),due)
        self.assertEqual(calculate(record(),{date(2026,7,31)})['fd_due_date'],date(2026,8,4))
    def test_decision_time_independent_and_either_direction(self):
        for hour in (9,17,23):
            r=record(registered_at=datetime(2026,7,31,hour));self.assertEqual(r['calculated_decision_date'],date(2026,8,6))
            for col in ('kc_sent_date','np_sent_date'):
                self.assertEqual(calculate(dict(r,**{col:date(2026,8,1)}),set())['calculated_decision_date'],date(2026,8,11))
    def test_only_completed_archive_two_calendar_months(self):
        r=record(registered_at=datetime(2026,12,31,12));at=datetime(2027,2,28,12)
        self.assertFalse(archive_due(r,at));r['decision_date']=date(2027,1,2)
        self.assertFalse(archive_due(r,at-timedelta(seconds=1)));self.assertTrue(archive_due(r,at))
    def test_fifty_users_isolated_by_id_with_identical_names(self):
        people=[{'id':i+1,'role':i if i<4 else 4 if i<27 else 5,'name':'Одинаковое ФИО'} for i in range(50)]
        for p in people[4:]:
            col='fd_executor_id' if p['role']==4 else 'uoso_executor_id';r=record(**{col:p['id']})
            for other in people[4:]:self.assertEqual(can_view(r,other),other['id']==p['id'])
            p['name']='Изменённое ФИО';self.assertTrue(can_view(r,p))
    def test_fd_required_and_terminal_access(self):
        u={'id':5,'role':4};r=record(fd_executor_id=5)
        with self.assertRaises(Invalid):apply_changes(r,{'12':'Проведена'},u,set())
        r=apply_changes(r,{'12':'Проведена','10':'2026-08-01','11':'2026-08-01','13':'001'},u,set())
        self.assertFalse(can_view(r,u))
    def test_uoso_cannot_edit_fd_or_other_assignment(self):
        r=record(uoso_executor_id=6);u={'id':6,'role':5}
        with self.assertRaises(PermissionError):apply_changes(r,{'12':'Недозвон'},u,set())
        with self.assertRaises(PermissionError):apply_changes(r,{'15':'8'},u,set())
    def test_return_time_seconds_preserved_no_calculation_effect(self):
        u={'id':6,'role':5};r=record(uoso_executor_id=6)
        a=apply_changes(r,{'14':'2026-09-14T10:00:01'},u,set());b=apply_changes(a,{'14':'2026-09-14T10:00:02'},u,set())
        self.assertNotEqual(a['return_date'],b['return_date']);self.assertEqual(a['fd_due_date'],b['fd_due_date']);self.assertEqual(a['calculated_decision_date'],b['calculated_decision_date'])
    def test_export_45_days_inclusive(self):
        self.assertEqual(export_period('2026-08-01','2026-09-14'),(date(2026,8,1),date(2026,9,14)))
        with self.assertRaises(Invalid):export_period('2026-08-01','2026-09-15')
    def test_operator_payload_has_no_stage_information(self):
        data=record_payload(record(fd_executor_id=5,fd_status='Недозвон'),1)['data']
        self.assertTrue(all(v=='' for v in data[8:]));self.assertEqual(data[2],'001')
    def test_import_preserves_text_identifiers_and_rejects_invalid_registration(self):
        values=['31.07.2026','Заявка','0001','31.07.2026 17:00:00','09-00','00002','ЦАО','Тверской']
        r=web.import_rows({'header':HEADERS[:8],'rows':[values]},set())[0];self.assertEqual(r['request_id'],'0001');self.assertEqual(r['citizen_id'],'00002')
        values[3]='невозможно прочитать'
        with self.assertRaises(Invalid):web.import_rows({'header':HEADERS[:8],'rows':[values]},set())
    def test_import_9999_rows_and_limit(self):
        v=['31.07.2026','Заявка','1','31.07.2026 17:00:00','09-00','2','ЦАО','Тверской']
        self.assertEqual(len(web.import_rows({'header':HEADERS[:8],'rows':[v]*9999},set())),9999)
        with self.assertRaises(Invalid):web.import_rows({'header':HEADERS[:8],'rows':[v]*10000},set())

class SecurityTests(unittest.TestCase):
    def setUp(self):self.client=web.app.test_client()
    def test_api_requires_session(self):
        for url in ('/api/state','/api/requests','/api/export','/api/notifications','/api/audit','/api/templates'):
            self.assertEqual(self.client.get(url).status_code,401)
    def test_origin_required_for_login(self):
        self.assertEqual(self.client.post('/api/auth/login',json={}).status_code,403)
        self.assertEqual(self.client.post('/api/auth/login',json={},headers={'Origin':'https://evil.example'}).status_code,403)
    def test_static_has_no_demo_code_and_security_headers(self):
        r=self.client.get('/');self.assertEqual(r.status_code,200);self.assertIn(b'/server.js',r.data);self.assertNotIn(b'/app.js',r.data);self.assertEqual(r.headers['X-Frame-Options'],'DENY');self.assertIn("script-src 'self'",r.headers['Content-Security-Policy'])
        r.close()
        self.assertEqual(self.client.get('/app.js').status_code,404)
        self.assertEqual(self.client.get('/../deploy/.env').status_code,404)
    def test_csrf_stable_across_tabs(self):
        self.assertEqual(web.csrf_for('session'),web.csrf_for('session'));self.assertNotEqual(web.csrf_for('session'),web.csrf_for('other'))
    def test_bcrypt_no_plaintext(self):
        h=web.hash_password('test-password-123');self.assertTrue(h.startswith('$2b$'));self.assertTrue(web.bcrypt.checkpw(b'test-password-123',h.encode()))
        with self.assertRaises(Invalid):web.hash_password('short')
    def test_real_middleware_csrf_and_mandatory_change(self):
        csrf=web.csrf_for('session');u={'id':1,'role':0,'full_name':'Администратор','login':'admin','active':True,'created_at':datetime.now(timezone.utc),'must_change_password':True,'csrf_token_hash':web.digest(csrf)}
        class DB:
            def execute(self,*args):return self
            def fetchone(self):return u
        @contextmanager
        def connection():yield DB()
        self.client.set_cookie('skz_session','session')
        with patch.object(web,'connection',connection):
            self.assertEqual(self.client.get('/api/state').status_code,403)
            self.assertTrue(self.client.get('/api/me').json['user']['mustChange'])
            self.assertEqual(self.client.post('/api/auth/logout',json={},headers={'Origin':web.ORIGIN}).status_code,403)
            self.assertEqual(self.client.post('/api/auth/logout',json={},headers={'Origin':web.ORIGIN,'X-CSRF-Token':csrf}).status_code,200)

if __name__=='__main__':unittest.main(verbosity=2)
