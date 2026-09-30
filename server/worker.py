"""One dedicated worker; tasks are idempotent and serialized by a DB advisory lock."""
import logging,time
from db import connection

def tick():
    with connection() as db:
        if not db.execute('SELECT pg_try_advisory_xact_lock(4857002) AS locked').fetchone()['locked']:return
        db.execute("""WITH archived AS (
          UPDATE requests SET archived_at=now(),revision=revision+1
          WHERE archived_at IS NULL AND decision_date IS NOT NULL
          AND registered_at+interval '2 months' <= now() AT TIME ZONE 'Europe/Moscow'
          RETURNING id,archived_at)
          INSERT INTO action_log(request_id,user_id,action,after_values)
          SELECT id,NULL,'Автоматическая архивация',jsonb_build_object('archived_at',archived_at) FROM archived""")
        db.execute("""INSERT INTO notifications(recipient_id,request_id,type,due_date,message)
          SELECT u.id,r.id,'return',r.return_date,'Возврат к заявке'
          FROM requests r JOIN users u ON u.active AND
          ((u.id=r.fd_executor_id AND u.role=4 AND r.fd_status IS DISTINCT FROM 'Проведена') OR
           (u.id=r.uoso_executor_id AND u.role=5 AND r.decision_date IS NULL))
          WHERE r.archived_at IS NULL AND r.return_date <= now() AT TIME ZONE 'Europe/Moscow'
          ON CONFLICT (recipient_id,request_id,due_date) WHERE type='return' DO NOTHING""")
        db.execute('DELETE FROM sessions WHERE expires_at<=now()')

if __name__=='__main__':
    logging.basicConfig(level=logging.INFO)
    while True:
        try:tick()
        except Exception:logging.exception('Background task failed')
        time.sleep(30)
