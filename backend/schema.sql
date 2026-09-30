-- Initial migration. Business timestamps represent Europe/Moscow time.
BEGIN;
CREATE TABLE users (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 full_name text NOT NULL,
 login text NOT NULL UNIQUE,
 password_hash text NOT NULL,
 role smallint NOT NULL CHECK (role BETWEEN 0 AND 5),
 active boolean NOT NULL DEFAULT true,
 must_change_password boolean NOT NULL DEFAULT true,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX single_operator_role ON users(role) WHERE role < 4;
CREATE TABLE holidays (date date PRIMARY KEY);
CREATE TABLE requests (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 source_date text NOT NULL,
 title text NOT NULL,
 request_id text NOT NULL UNIQUE,
 registered_at timestamp NOT NULL,
 export_time text NOT NULL,
 citizen_id text NOT NULL,
 district text NOT NULL,
 area text NOT NULL,
 fd_due_date date,
 fd_executor_id bigint REFERENCES users(id),
 fd_plan_date date,
 fd_fact_date date,
 fd_status text CHECK (fd_status IN ('Проведена','Отказ от ФД','Недозвон','Госпитализация','Помещен в стационарное учреждение ГЦ/СД')),
 questionnaire_number text,
 return_date timestamp,
 uoso_executor_id bigint REFERENCES users(id),
 kc_sent_date date,
 kc_return_date date,
 np_sent_date date,
 np_return_date date,
 calculated_decision_date date,
 decision_date date,
 status text GENERATED ALWAYS AS (CASE WHEN decision_date IS NULL THEN 'Не завершена' ELSE 'Завершена' END) STORED,
 uploaded_by bigint NOT NULL REFERENCES users(id),
 archived_at timestamptz,
 revision bigint NOT NULL DEFAULT 1,
 CHECK (fd_status IS DISTINCT FROM 'Проведена' OR (fd_plan_date IS NOT NULL AND fd_fact_date IS NOT NULL AND NULLIF(questionnaire_number,'') IS NOT NULL))
);
CREATE INDEX requests_registered ON requests(registered_at);
CREATE INDEX requests_fd_assigned ON requests(fd_executor_id,fd_status) WHERE archived_at IS NULL;
CREATE INDEX requests_uoso_assigned ON requests(uoso_executor_id,status) WHERE archived_at IS NULL;
CREATE INDEX requests_citizen ON requests(citizen_id);
CREATE TABLE action_log (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 request_id bigint REFERENCES requests(id),
 user_id bigint REFERENCES users(id),
 occurred_at timestamptz NOT NULL DEFAULT now(),
 action text NOT NULL,
 before_values jsonb,
 after_values jsonb
);
CREATE INDEX action_log_request ON action_log(request_id,occurred_at);
CREATE TABLE notifications (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 recipient_id bigint NOT NULL REFERENCES users(id),
 request_id bigint REFERENCES requests(id),
 type text NOT NULL DEFAULT 'new' CHECK (type IN ('new','return')),
 due_date timestamp,
 message text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 read_at timestamptz,
 processed_at timestamptz
);
CREATE UNIQUE INDEX one_return_reminder_per_date ON notifications(recipient_id,request_id,due_date) WHERE type='return';
CREATE INDEX notifications_recipient_pending ON notifications(recipient_id,id DESC) WHERE processed_at IS NULL;
CREATE INDEX notifications_request_pending ON notifications(request_id) WHERE processed_at IS NULL;
CREATE TABLE template_versions (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 filename text NOT NULL,
 content bytea NOT NULL,
 uploaded_by bigint NOT NULL REFERENCES users(id),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE sessions (
 token_hash text PRIMARY KEY,
 user_id bigint NOT NULL REFERENCES users(id),
 csrf_token_hash text NOT NULL,
 expires_at timestamptz NOT NULL
);
COMMIT;
