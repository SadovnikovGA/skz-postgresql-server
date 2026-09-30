"""Business rules independent from transport and persistence."""
from datetime import date, datetime, timedelta
from calendar import monthrange
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Europe/Moscow')
STATUSES = ['Проведена', 'Отказ от ФД', 'Недозвон', 'Госпитализация', 'Помещен в стационарное учреждение ГЦ/СД']
COLUMNS = ['source_date','title','request_id','registered_at','export_time','citizen_id','district','area','fd_due_date','fd_executor_id','fd_plan_date','fd_fact_date','fd_status','questionnaire_number','return_date','uoso_executor_id','kc_sent_date','kc_return_date','np_sent_date','np_return_date','calculated_decision_date','decision_date','status']
HEADERS = ['Дата','Наименование заявки','ИД заявки','Дата регистрации заявки','Время выгрузки','ИД гражданина','Округ','Район','Дата до которой необходимо согласовать ФД','Исполнитель ФД','Дата План ФД','Дата Факт ФД','Статус ФД','Номер анкеты','Дата возврата к заявке','Исполнитель УОСО','Дата направления в КЦ','Дата возврата из КЦ','Дата направления Запроса к НП','Дата Возврата от НП','Расчётная дата решения','Дата решения','Статус заявки']
DATE_FIELDS = {10,11,16,17,18,19,21}
EDITABLE = {0:set([0,1,3,4,5,6,7,10,11,12,13,14,16,17,18,19,21]),4:{10,11,12,13,14},5:{14,16,17,18,19,21}}

class Invalid(ValueError):
    pass

def now():
    return datetime.now(TZ).replace(tzinfo=None)

def parse_datetime(value):
    if isinstance(value, datetime):
        return value.astimezone(TZ).replace(tzinfo=None) if value.tzinfo else value
    value = str(value).strip()
    for fmt in ('%d.%m.%Y %H:%M:%S','%d.%m.%Y %H:%M','%Y-%m-%dT%H:%M:%S','%Y-%m-%dT%H:%M','%Y-%m-%d %H:%M:%S','%Y-%m-%d','%d.%m.%Y'):
        try:
            return datetime.strptime(value,fmt)
        except ValueError:
            pass
    raise Invalid('Не удалось прочитать дату и время. Используйте ДД.ММ.ГГГГ ЧЧ:ММ:СС.')

def parse_date(value):
    if isinstance(value, date) and not isinstance(value,datetime):
        return value
    return parse_datetime(value).date()

def add_work(value, days, holidays):
    d = value.date() if isinstance(value,datetime) else value
    while days:
        d += timedelta(days=1)
        if d.weekday()<5 and d not in holidays:
            days -= 1
    return d

def calculate(row, holidays):
    registered = row['registered_at']
    early = registered.hour*3600+registered.minute*60+registered.second <= 17*3600
    work = registered.weekday()<5 and registered.date() not in holidays
    row['fd_due_date'] = add_work(registered,1 if work and early else 2,holidays)
    row['calculated_decision_date'] = add_work(registered,7 if row.get('kc_sent_date') or row.get('np_sent_date') else 4,holidays)
    return row

def archive_due(row, at=None):
    if row.get('archived_at'):
        return True
    if not row.get('decision_date'):
        return False
    d = row['registered_at'];month=d.month+2;year=d.year+(month-1)//12;month=(month-1)%12+1
    threshold=d.replace(year=year,month=month,day=min(d.day,monthrange(year,month)[1]))
    return (at or now())>=threshold

def can_view(row, user):
    role=user['role']
    if archive_due(row) and role!=0:
        return False
    if role==1:
        return row['uploaded_by']==user['id']
    if role==4:
        return row.get('fd_executor_id')==user['id'] and row.get('fd_status')!='Проведена'
    if role==5:
        return row.get('uoso_executor_id')==user['id'] and row.get('decision_date') is None
    return True

def apply_changes(row, changes, user, holidays):
    if not can_view(row,user) or archive_due(row):
        raise PermissionError('Редактирование заявки недоступно')
    allowed = EDITABLE.get(user['role'],set())
    updated=dict(row)
    for raw, value in changes.items():
        try:
            i=int(raw)
        except (TypeError,ValueError):
            raise Invalid('Неизвестное поле')
        if i not in allowed:
            raise PermissionError('Изменение поля запрещено')
        if value in ('',None):
            value=None
        elif i in DATE_FIELDS:
            value=parse_date(value)
        elif i in (3,14):
            value=parse_datetime(value)
        else:
            value=str(value)
        if i in (0,1,3,4,5,6,7) and value is None:
            raise Invalid('Заполните обязательные поля')
        if i==12 and value is not None and value not in STATUSES:
            raise Invalid('Недопустимый Статус ФД')
        updated[COLUMNS[i]]=value
    if user['role']==4 and not updated.get('fd_status'):
        raise Invalid('Заполните обязательные поля')
    if updated.get('fd_status')=='Проведена' and any(not updated.get(k) for k in ('fd_plan_date','fd_fact_date','questionnaire_number')):
        raise Invalid('Заполните обязательные поля')
    return calculate(updated,holidays)

def export_period(start,end):
    start,end=parse_date(start),parse_date(end)
    if end<start:
        raise Invalid('Начало периода должно быть не позже окончания')
    if (end-start).days+1>45:
        raise Invalid('Максимальный период — 45 дней')
    return start,end

def public_user(u):
    return dict(id=u['id'],name=u['full_name'],login=u['login'],role=u['role'],active=u['active'],created=u['created_at'].isoformat(),mustChange=u['must_change_password'])

def record_payload(r, role=0):
    data=[]
    for i,col in enumerate(COLUMNS):
        v=r.get(col)
        if role==1 and i>=8:
            v=None
        if isinstance(v,datetime):
            v=v.strftime('%d.%m.%Y %H:%M:%S') if i==3 else v.isoformat(timespec='seconds')
        elif isinstance(v,date):
            v=v.isoformat()
        data.append(v if v is not None else '')
    return dict(data=data,owner=r['uploaded_by'],revision=r['revision'],archived=archive_due(r),isNew=bool(r.get('is_new')))
