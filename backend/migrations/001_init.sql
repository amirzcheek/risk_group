-- ───────────────────────────────────────────────────────────────────────────
-- Миграция 001: таблицы признаков, прогнозов и журнала доступа (Postgres).
--
-- Хранилище системы группы риска. Сюда пишутся вычисленные признаки, результаты
-- скоринга и журнал просмотров списка риска (требование этики/безопасности).
-- Для локальной разработки без Postgres код использует эквивалентные таблицы в
-- SQLite (см. storage.py) — DDL здесь является каноническим описанием схемы.
-- ───────────────────────────────────────────────────────────────────────────

-- Признаки на момент отсечки (для аудита и переиспользования).
CREATE TABLE IF NOT EXISTS features (
    id            BIGSERIAL PRIMARY KEY,
    student_id    TEXT        NOT NULL,
    term          TEXT        NOT NULL,
    cutoff_week   INTEGER     NOT NULL,
    faculty       TEXT,
    study_group   TEXT,
    program       TEXT,
    features      JSONB       NOT NULL,          -- словарь имя→значение признака
    computed_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (student_id, term, cutoff_week)
);
CREATE INDEX IF NOT EXISTS idx_features_term ON features (term);

-- Прогнозы риска (результат батч-скоринга).
CREATE TABLE IF NOT EXISTS predictions (
    id            BIGSERIAL PRIMARY KEY,
    run_id        TEXT        NOT NULL,          -- идентификатор прогона скоринга
    student_id    TEXT        NOT NULL,
    term          TEXT        NOT NULL,
    faculty       TEXT,
    study_group   TEXT,
    program       TEXT,
    risk_proba    DOUBLE PRECISION NOT NULL,     -- калиброванная вероятность 0..1
    risk_level    TEXT        NOT NULL,          -- high | medium | low
    is_flagged    BOOLEAN     NOT NULL DEFAULT FALSE,  -- попал ли в группу риска (топ-X%)
    top_factors   JSONB       NOT NULL,          -- топ-факторы с вкладами (объяснение)
    model_version TEXT,                          -- время обучения модели
    scored_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_pred_run ON predictions (run_id);
CREATE INDEX IF NOT EXISTS idx_pred_student ON predictions (student_id);
CREATE INDEX IF NOT EXISTS idx_pred_flag ON predictions (is_flagged);
CREATE INDEX IF NOT EXISTS idx_pred_faculty_group ON predictions (faculty, study_group);

-- Реестр прогонов скоринга (метаданные батча).
CREATE TABLE IF NOT EXISTS score_runs (
    run_id        TEXT        PRIMARY KEY,
    term          TEXT,
    cutoff_week   INTEGER,
    n_students    INTEGER,
    n_flagged     INTEGER,
    threshold     DOUBLE PRECISION,
    model_version TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Журнал доступа к списку риска (кто и какой список смотрел).
-- Требование этики: список риска чувствителен, доступ должен логироваться.
CREATE TABLE IF NOT EXISTS access_log (
    id            BIGSERIAL PRIMARY KEY,
    actor         TEXT,                          -- идентификатор/роль смотрящего
    action        TEXT        NOT NULL,          -- view_risk_list | view_student | ...
    target        TEXT,                          -- факультет/группа/student_id
    detail        JSONB,
    at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_access_at ON access_log (at);
