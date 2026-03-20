import sqlite3
import uuid
from datetime import datetime


def get_conn(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path):
    conn = get_conn(db_path)
    c = conn.cursor()

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
            editado_em TEXT,
            FOREIGN KEY (imovel_id) REFERENCES imoveis(id)
        )
    """)
    conn.commit()

    # Migration: add usuario_id to imoveis if table existed without it
    try:
        c.execute("ALTER TABLE imoveis ADD COLUMN usuario_id TEXT NOT NULL DEFAULT ''")
        conn.commit()
    except Exception:
        pass  # Column already exists

    conn.close()


def row_to_dict(row):
    if row is None:
        return None
    return dict(row)


# ─── USUARIOS ────────────────────────────────────────────────────────────────

def add_usuario(db_path, nome, email, senha_hash):
    conn = get_conn(db_path)
    c = conn.cursor()
    user_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    c.execute(
        "INSERT INTO usuarios (id, nome, email, senha_hash, criado_em) VALUES (?, ?, ?, ?, ?)",
        (user_id, nome, email, senha_hash, now)
    )
    conn.commit()
    c.execute("SELECT * FROM usuarios WHERE id = ?", (user_id,))
    row = row_to_dict(c.fetchone())
    conn.close()
    return row


def get_usuario_by_email(db_path, email):
    conn = get_conn(db_path)
    c = conn.cursor()
    c.execute("SELECT * FROM usuarios WHERE email = ?", (email,))
    row = row_to_dict(c.fetchone())
    conn.close()
    return row


def get_usuario_by_id(db_path, user_id):
    conn = get_conn(db_path)
    c = conn.cursor()
    c.execute("SELECT * FROM usuarios WHERE id = ?", (user_id,))
    row = row_to_dict(c.fetchone())
    conn.close()
    return row


# ─── IMOVEIS ─────────────────────────────────────────────────────────────────

def get_imoveis(db_path, usuario_id=None):
    conn = get_conn(db_path)
    c = conn.cursor()
    if usuario_id:
        c.execute("SELECT * FROM imoveis WHERE usuario_id = ? ORDER BY criado_em DESC", (usuario_id,))
    else:
        c.execute("SELECT * FROM imoveis ORDER BY criado_em DESC")
    rows = [row_to_dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def add_imovel(db_path, data, usuario_id=''):
    conn = get_conn(db_path)
    c = conn.cursor()
    imovel_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    c.execute("""
        INSERT INTO imoveis (id, usuario_id, nome, rua, numero, complemento, cep, data_arrematacao, obs, criado_em)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        imovel_id,
        usuario_id,
        data.get('nome', ''),
        data.get('rua', ''),
        data.get('numero', ''),
        data.get('complemento', ''),
        data.get('cep', ''),
        data.get('data_arrematacao', ''),
        data.get('obs', ''),
        now
    ))
    conn.commit()
    c.execute("SELECT * FROM imoveis WHERE id = ?", (imovel_id,))
    row = row_to_dict(c.fetchone())
    conn.close()
    return row


# ─── CUSTOS ──────────────────────────────────────────────────────────────────

def get_custos(db_path, imovel_id):
    conn = get_conn(db_path)
    c = conn.cursor()
    c.execute("SELECT * FROM custos WHERE imovel_id = ? ORDER BY data_pagamento DESC, registrado_em DESC", (imovel_id,))
    rows = [row_to_dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_all_custos(db_path):
    conn = get_conn(db_path)
    c = conn.cursor()
    c.execute("SELECT * FROM custos ORDER BY data_pagamento DESC, registrado_em DESC")
    rows = [row_to_dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def add_custo(db_path, data):
    conn = get_conn(db_path)
    c = conn.cursor()
    custo_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    c.execute("""
        INSERT INTO custos (
            id, imovel_id, nicho, descricao, valor, data_pagamento,
            forma_pagamento, favorecido, observacoes,
            comprovante_path, comprovante_nome, comprovante_tipo,
            registrado_em, editado_em
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        custo_id,
        data.get('imovel_id', ''),
        data.get('nicho', ''),
        data.get('descricao', ''),
        float(data.get('valor', 0)),
        data.get('data_pagamento', ''),
        data.get('forma_pagamento', ''),
        data.get('favorecido', ''),
        data.get('observacoes', ''),
        data.get('comprovante_path', ''),
        data.get('comprovante_nome', ''),
        data.get('comprovante_tipo', ''),
        now,
        now
    ))
    conn.commit()
    c.execute("SELECT * FROM custos WHERE id = ?", (custo_id,))
    row = row_to_dict(c.fetchone())
    conn.close()
    return row


def update_custo(db_path, custo_id, data):
    conn = get_conn(db_path)
    c = conn.cursor()
    now = datetime.now().isoformat()

    fields = ['nicho', 'descricao', 'valor', 'data_pagamento', 'forma_pagamento', 'favorecido', 'observacoes']
    set_clauses = [f"{f} = ?" for f in fields]
    values = [
        data.get('nicho', ''),
        data.get('descricao', ''),
        float(data.get('valor', 0)),
        data.get('data_pagamento', ''),
        data.get('forma_pagamento', ''),
        data.get('favorecido', ''),
        data.get('observacoes', ''),
    ]

    if data.get('comprovante_path') is not None:
        set_clauses += ['comprovante_path = ?', 'comprovante_nome = ?', 'comprovante_tipo = ?']
        values += [data.get('comprovante_path', ''), data.get('comprovante_nome', ''), data.get('comprovante_tipo', '')]

    set_clauses.append('editado_em = ?')
    values.append(now)
    values.append(custo_id)

    sql = f"UPDATE custos SET {', '.join(set_clauses)} WHERE id = ?"
    c.execute(sql, values)
    conn.commit()
    c.execute("SELECT * FROM custos WHERE id = ?", (custo_id,))
    row = row_to_dict(c.fetchone())
    conn.close()
    return row


def delete_custo(db_path, custo_id):
    conn = get_conn(db_path)
    c = conn.cursor()
    c.execute("SELECT comprovante_path FROM custos WHERE id = ?", (custo_id,))
    row = c.fetchone()
    path = row['comprovante_path'] if row else None
    c.execute("DELETE FROM custos WHERE id = ?", (custo_id,))
    conn.commit()
    conn.close()
    return path


def get_custo(db_path, custo_id):
    conn = get_conn(db_path)
    c = conn.cursor()
    c.execute("SELECT * FROM custos WHERE id = ?", (custo_id,))
    row = row_to_dict(c.fetchone())
    conn.close()
    return row
