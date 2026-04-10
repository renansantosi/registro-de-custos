import os
import uuid
from datetime import datetime

DATABASE_URL = os.environ.get('DATABASE_URL', '')
USE_PG = bool(DATABASE_URL)

if USE_PG:
    import psycopg2
    import psycopg2.extras
    PH = '%s'
else:
    import sqlite3
    PH = '?'


def _pg_url():
    url = DATABASE_URL
    if url.startswith('postgres://'):
        url = 'postgresql://' + url[len('postgres://'):]
    return url


def get_conn(db_path=None):
    if USE_PG:
        return psycopg2.connect(_pg_url(), cursor_factory=psycopg2.extras.RealDictCursor)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def to_dict(row):
    if row is None:
        return None
    return dict(row)


def init_db(db_path=None):
    conn = get_conn(db_path)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS viabilidade_analises (
            id TEXT PRIMARY KEY,
            usuario_id TEXT NOT NULL,
            nome_edital TEXT,
            nome_matricula TEXT,
            analise TEXT NOT NULL,
            criado_em TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            senha_hash TEXT NOT NULL,
            criado_em TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS imoveis (
            id TEXT PRIMARY KEY,
            usuario_id TEXT NOT NULL DEFAULT '',
            nome TEXT NOT NULL,
            rua TEXT,
            numero TEXT,
            complemento TEXT,
            cep TEXT,
            data_arrematacao TEXT,
            obs TEXT,
            criado_em TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS custos (
            id TEXT PRIMARY KEY,
            imovel_id TEXT NOT NULL,
            nicho TEXT NOT NULL,
            descricao TEXT NOT NULL,
            valor REAL NOT NULL,
            data_pagamento TEXT NOT NULL,
            forma_pagamento TEXT NOT NULL,
            favorecido TEXT,
            observacoes TEXT,
            comprovante_path TEXT,
            comprovante_nome TEXT,
            comprovante_tipo TEXT,
            registrado_em TEXT,
            editado_em TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS reset_tokens (
            token TEXT PRIMARY KEY,
            usuario_id TEXT NOT NULL,
            expira_em TEXT NOT NULL
        )
    """)

    conn.commit()

    try:
        c.execute("ALTER TABLE imoveis ADD COLUMN usuario_id TEXT NOT NULL DEFAULT ''")
        conn.commit()
    except Exception:
        if USE_PG:
            conn.rollback()

    try:
        c.execute("ALTER TABLE usuarios ADD COLUMN avatar_path TEXT DEFAULT ''")
        conn.commit()
    except Exception:
        if USE_PG:
            conn.rollback()

    c.execute("""
        CREATE TABLE IF NOT EXISTS parceiros (
            id TEXT PRIMARY KEY,
            imovel_id TEXT NOT NULL,
            nome TEXT,
            email TEXT NOT NULL,
            notificar INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT
        )
    """)
    conn.commit()

    conn.close()


def get_imovel_by_id(db_path, imovel_id):
    conn = get_conn(db_path)
    c = conn.cursor()
    c.execute(f"SELECT * FROM imoveis WHERE id = {PH}", (imovel_id,))
    row = to_dict(c.fetchone())
    conn.close()
    return row


def get_parceiros(db_path, imovel_id):
    conn = get_conn(db_path)
    c = conn.cursor()
    c.execute(f"SELECT * FROM parceiros WHERE imovel_id = {PH} ORDER BY criado_em", (imovel_id,))
    rows = [to_dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def add_parceiro(db_path, imovel_id, nome, email, notificar=True):
    conn = get_conn(db_path)
    c = conn.cursor()
    pid = str(uuid.uuid4())
    now = datetime.now().isoformat()
    c.execute(
        f"INSERT INTO parceiros (id, imovel_id, nome, email, notificar, criado_em) VALUES ({PH},{PH},{PH},{PH},{PH},{PH})",
        (pid, imovel_id, nome or '', email, 1 if notificar else 0, now)
    )
    conn.commit()
    c.execute(f"SELECT * FROM parceiros WHERE id = {PH}", (pid,))
    row = to_dict(c.fetchone())
    conn.close()
    return row


def delete_parceiro(db_path, parceiro_id):
    conn = get_conn(db_path)
    c = conn.cursor()
    c.execute(f"DELETE FROM parceiros WHERE id = {PH}", (parceiro_id,))
    conn.commit()
    conn.close()


def update_parceiro_notificar(db_path, parceiro_id, notificar):
    conn = get_conn(db_path)
    c = conn.cursor()
    c.execute(f"UPDATE parceiros SET notificar = {PH} WHERE id = {PH}", (1 if notificar else 0, parceiro_id))
    conn.commit()
    conn.close()


# ─── USUARIOS ────────────────────────────────────────────────────────────────

def add_usuario(db_path, nome, email, senha_hash):
    conn = get_conn(db_path)
    c = conn.cursor()
    user_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    c.execute(
        f"INSERT INTO usuarios (id, nome, email, senha_hash, criado_em) VALUES ({PH},{PH},{PH},{PH},{PH})",
        (user_id, nome, email, senha_hash, now)
    )
    conn.commit()
    c.execute(f"SELECT * FROM usuarios WHERE id = {PH}", (user_id,))
    row = to_dict(c.fetchone())
    conn.close()
    return row


def get_usuario_by_email(db_path, email):
    conn = get_conn(db_path)
    c = conn.cursor()
    c.execute(f"SELECT * FROM usuarios WHERE email = {PH}", (email,))
    row = to_dict(c.fetchone())
    conn.close()
    return row


def get_usuario_by_id(db_path, user_id):
    conn = get_conn(db_path)
    c = conn.cursor()
    c.execute(f"SELECT * FROM usuarios WHERE id = {PH}", (user_id,))
    row = to_dict(c.fetchone())
    conn.close()
    return row


# ─── IMOVEIS ─────────────────────────────────────────────────────────────────

def get_imoveis(db_path, usuario_id=None):
    conn = get_conn(db_path)
    c = conn.cursor()
    if usuario_id:
        c.execute(f"SELECT * FROM imoveis WHERE usuario_id = {PH} ORDER BY criado_em DESC", (usuario_id,))
    else:
        c.execute("SELECT * FROM imoveis ORDER BY criado_em DESC")
    rows = [to_dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def add_imovel(db_path, data, usuario_id=''):
    conn = get_conn(db_path)
    c = conn.cursor()
    imovel_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    c.execute(f"""
        INSERT INTO imoveis (id, usuario_id, nome, rua, numero, complemento, cep, data_arrematacao, obs, criado_em)
        VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})
    """, (
        imovel_id, usuario_id,
        data.get('nome', ''), data.get('rua', ''), data.get('numero', ''),
        data.get('complemento', ''), data.get('cep', ''),
        data.get('data_arrematacao', ''), data.get('obs', ''), now
    ))
    conn.commit()
    c.execute(f"SELECT * FROM imoveis WHERE id = {PH}", (imovel_id,))
    row = to_dict(c.fetchone())
    conn.close()
    return row


# ─── CUSTOS ──────────────────────────────────────────────────────────────────

def get_custos(db_path, imovel_id):
    conn = get_conn(db_path)
    c = conn.cursor()
    c.execute(f"SELECT * FROM custos WHERE imovel_id = {PH} ORDER BY data_pagamento DESC, registrado_em DESC", (imovel_id,))
    rows = [to_dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_all_custos(db_path):
    conn = get_conn(db_path)
    c = conn.cursor()
    c.execute("SELECT * FROM custos ORDER BY data_pagamento DESC, registrado_em DESC")
    rows = [to_dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def add_custo(db_path, data):
    conn = get_conn(db_path)
    c = conn.cursor()
    custo_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    c.execute(f"""
        INSERT INTO custos (
            id, imovel_id, nicho, descricao, valor, data_pagamento,
            forma_pagamento, favorecido, observacoes,
            comprovante_path, comprovante_nome, comprovante_tipo,
            registrado_em, editado_em
        ) VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})
    """, (
        custo_id,
        data.get('imovel_id', ''), data.get('nicho', ''), data.get('descricao', ''),
        float(data.get('valor', 0)), data.get('data_pagamento', ''),
        data.get('forma_pagamento', ''), data.get('favorecido', ''),
        data.get('observacoes', ''), data.get('comprovante_path', ''),
        data.get('comprovante_nome', ''), data.get('comprovante_tipo', ''),
        now, now
    ))
    conn.commit()
    c.execute(f"SELECT * FROM custos WHERE id = {PH}", (custo_id,))
    row = to_dict(c.fetchone())
    conn.close()
    return row


def update_custo(db_path, custo_id, data):
    conn = get_conn(db_path)
    c = conn.cursor()
    now = datetime.now().isoformat()

    fields = ['nicho', 'descricao', 'valor', 'data_pagamento', 'forma_pagamento', 'favorecido', 'observacoes']
    set_clauses = [f"{f} = {PH}" for f in fields]
    values = [
        data.get('nicho', ''), data.get('descricao', ''),
        float(data.get('valor', 0)), data.get('data_pagamento', ''),
        data.get('forma_pagamento', ''), data.get('favorecido', ''),
        data.get('observacoes', ''),
    ]

    if data.get('comprovante_path') is not None:
        set_clauses += [f'comprovante_path = {PH}', f'comprovante_nome = {PH}', f'comprovante_tipo = {PH}']
        values += [data.get('comprovante_path', ''), data.get('comprovante_nome', ''), data.get('comprovante_tipo', '')]

    set_clauses.append(f'editado_em = {PH}')
    values.append(now)
    values.append(custo_id)

    c.execute(f"UPDATE custos SET {', '.join(set_clauses)} WHERE id = {PH}", values)
    conn.commit()
    c.execute(f"SELECT * FROM custos WHERE id = {PH}", (custo_id,))
    row = to_dict(c.fetchone())
    conn.close()
    return row


def delete_custo(db_path, custo_id):
    conn = get_conn(db_path)
    c = conn.cursor()
    c.execute(f"SELECT comprovante_path FROM custos WHERE id = {PH}", (custo_id,))
    row = c.fetchone()
    path = row['comprovante_path'] if row else None
    c.execute(f"DELETE FROM custos WHERE id = {PH}", (custo_id,))
    conn.commit()
    conn.close()
    return path


def get_custo(db_path, custo_id):
    conn = get_conn(db_path)
    c = conn.cursor()
    c.execute(f"SELECT * FROM custos WHERE id = {PH}", (custo_id,))
    row = to_dict(c.fetchone())
    conn.close()
    return row


# ─── SENHA / RESET ───────────────────────────────────────────────────────────

def change_password(db_path, user_id, new_hash):
    conn = get_conn(db_path)
    c = conn.cursor()
    c.execute(f"UPDATE usuarios SET senha_hash = {PH} WHERE id = {PH}", (new_hash, user_id))
    conn.commit()
    conn.close()


def create_reset_token(db_path, user_id):
    import secrets
    from datetime import timedelta
    conn = get_conn(db_path)
    c = conn.cursor()
    c.execute(f"DELETE FROM reset_tokens WHERE usuario_id = {PH}", (user_id,))
    token = secrets.token_urlsafe(32)
    expira_em = (datetime.now() + timedelta(hours=1)).isoformat()
    c.execute(
        f"INSERT INTO reset_tokens (token, usuario_id, expira_em) VALUES ({PH},{PH},{PH})",
        (token, user_id, expira_em)
    )
    conn.commit()
    conn.close()
    return token


def get_valid_reset_token(db_path, token):
    conn = get_conn(db_path)
    c = conn.cursor()
    c.execute(f"SELECT * FROM reset_tokens WHERE token = {PH}", (token,))
    row = to_dict(c.fetchone())
    conn.close()
    if not row:
        return None
    if datetime.now().isoformat() > row['expira_em']:
        return None
    return row


def delete_reset_token(db_path, token):
    conn = get_conn(db_path)
    c = conn.cursor()
    c.execute(f"DELETE FROM reset_tokens WHERE token = {PH}", (token,))
    conn.commit()
    conn.close()


def update_usuario_avatar(db_path, user_id, avatar_path):
    conn = get_conn(db_path)
    c = conn.cursor()
    c.execute(f"UPDATE usuarios SET avatar_path = {PH} WHERE id = {PH}", (avatar_path, user_id))
    conn.commit()
    conn.close()


# ─── VIABILIDADE ANALISES ─────────────────────────────────────────────────────

def save_viabilidade(db_path, usuario_id, analise, nome_edital='', nome_matricula=''):
    conn = get_conn(db_path)
    c = conn.cursor()
    analise_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    c.execute(
        f"INSERT INTO viabilidade_analises (id, usuario_id, nome_edital, nome_matricula, analise, criado_em) VALUES ({PH},{PH},{PH},{PH},{PH},{PH})",
        (analise_id, usuario_id, nome_edital or '', nome_matricula or '', analise, now)
    )
    conn.commit()
    c.execute(f"SELECT * FROM viabilidade_analises WHERE id = {PH}", (analise_id,))
    row = to_dict(c.fetchone())
    conn.close()
    return row


def get_viabilidades(db_path, usuario_id):
    conn = get_conn(db_path)
    c = conn.cursor()
    c.execute(
        f"SELECT id, usuario_id, nome_edital, nome_matricula, criado_em FROM viabilidade_analises WHERE usuario_id = {PH} ORDER BY criado_em DESC",
        (usuario_id,)
    )
    rows = [to_dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_viabilidade_by_id(db_path, analise_id, usuario_id):
    conn = get_conn(db_path)
    c = conn.cursor()
    c.execute(
        f"SELECT * FROM viabilidade_analises WHERE id = {PH} AND usuario_id = {PH}",
        (analise_id, usuario_id)
    )
    row = to_dict(c.fetchone())
    conn.close()
    return row


def delete_viabilidade(db_path, analise_id, usuario_id):
    conn = get_conn(db_path)
    c = conn.cursor()
    c.execute(
        f"DELETE FROM viabilidade_analises WHERE id = {PH} AND usuario_id = {PH}",
        (analise_id, usuario_id)
    )
    conn.commit()
    conn.close()
