import os
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, send_file, redirect, url_for, render_template
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from database import (
    init_db, get_imoveis, add_imovel, get_custos, get_all_custos,
    add_custo, update_custo, delete_custo, get_custo,
    add_usuario, get_usuario_by_email, get_usuario_by_id
)
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from io import BytesIO

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
DB_PATH = os.path.join(BASE_DIR, 'registro.db')

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-leialopro-change-in-prod')
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024

login_manager = LoginManager(app)
login_manager.login_view = 'login_page'

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'}


# ─── User model ──────────────────────────────────────────────────────────────

class User(UserMixin):
    def __init__(self, row):
        self.id = row['id']
        self.nome = row['nome']
        self.email = row['email']


@login_manager.user_loader
def load_user(user_id):
    row = get_usuario_by_id(DB_PATH, user_id)
    return User(row) if row else None


@login_manager.unauthorized_handler
def unauthorized():
    if request.path.startswith('/api/') or request.is_json:
        return jsonify({'error': 'Sessao expirada. Faca login novamente.'}), 401
    return redirect(url_for('login_page'))


# ─── Helpers ─────────────────────────────────────────────────────────────────

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_upload(file):
    if not file or file.filename == '':
        return None, None, None
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    unique_name = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
    save_path = os.path.join(UPLOAD_FOLDER, unique_name)
    file.save(save_path)
    return unique_name, file.filename, file.content_type


def imovel_belongs_to_user(imovel_id, user_id):
    imoveis = get_imoveis(DB_PATH, user_id)
    return any(im['id'] == imovel_id for im in imoveis)


def custo_belongs_to_user(custo_id, user_id):
    custo = get_custo(DB_PATH, custo_id)
    if not custo:
        return False
    return imovel_belongs_to_user(custo['imovel_id'], user_id)


# ─── Auth pages ──────────────────────────────────────────────────────────────

@app.route('/login')
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return render_template('login.html')


@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.get_json(force=True) or {}
    email = (data.get('email') or '').strip().lower()
    senha = data.get('senha') or ''
    if not email or not senha:
        return jsonify({'error': 'E-mail e senha sao obrigatorios'}), 400
    usuario = get_usuario_by_email(DB_PATH, email)
    if not usuario or not check_password_hash(usuario['senha_hash'], senha):
        return jsonify({'error': 'E-mail ou senha incorretos'}), 401
    user = User(usuario)
    login_user(user, remember=True)
    return jsonify({'ok': True, 'nome': user.nome})


@app.route('/api/auth/register', methods=['POST'])
def api_register():
    data = request.get_json(force=True) or {}
    nome = (data.get('nome') or '').strip()
    email = (data.get('email') or '').strip().lower()
    senha = data.get('senha') or ''
    if not nome or not email or not senha:
        return jsonify({'error': 'Nome, e-mail e senha sao obrigatorios'}), 400
    if len(senha) < 6:
        return jsonify({'error': 'Senha deve ter pelo menos 6 caracteres'}), 400
    if get_usuario_by_email(DB_PATH, email):
        return jsonify({'error': 'E-mail ja cadastrado'}), 409
    senha_hash = generate_password_hash(senha)
    usuario = add_usuario(DB_PATH, nome, email, senha_hash)
    user = User(usuario)
    login_user(user, remember=True)
    return jsonify({'ok': True, 'nome': user.nome}), 201


@app.route('/api/auth/logout', methods=['POST'])
@login_required
def api_logout():
    logout_user()
    return jsonify({'ok': True})


@app.route('/api/auth/me')
@login_required
def api_me():
    return jsonify({'id': current_user.id, 'nome': current_user.nome, 'email': current_user.email})


# ─── Frontend ────────────────────────────────────────────────────────────────

@app.route('/')
@login_required
def index():
    return render_template('index.html', usuario_nome=current_user.nome)


# ─── IMOVEIS ─────────────────────────────────────────────────────────────────

@app.route('/api/imoveis', methods=['GET'])
@login_required
def api_get_imoveis():
    try:
        imoveis = get_imoveis(DB_PATH, current_user.id)
        for im in imoveis:
            custos = get_custos(DB_PATH, im['id'])
            im['total_investido'] = sum(c['valor'] for c in custos)
            im['num_custos'] = len(custos)
            im['num_docs'] = sum(1 for c in custos if c.get('comprovante_path'))
        return jsonify(imoveis)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/imoveis', methods=['POST'])
@login_required
def api_add_imovel():
    try:
        data = request.get_json(force=True)
        if not data or not data.get('nome'):
            return jsonify({'error': 'Nome e obrigatorio'}), 400
        imovel = add_imovel(DB_PATH, data, current_user.id)
        return jsonify(imovel), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─── CUSTOS ──────────────────────────────────────────────────────────────────

@app.route('/api/custos/<imovel_id>', methods=['GET'])
@login_required
def api_get_custos(imovel_id):
    try:
        if not imovel_belongs_to_user(imovel_id, current_user.id):
            return jsonify({'error': 'Acesso negado'}), 403
        custos = get_custos(DB_PATH, imovel_id)
        return jsonify(custos)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/custos', methods=['POST'])
@login_required
def api_add_custo():
    try:
        data = {}
        if request.content_type and 'multipart' in request.content_type:
            data = request.form.to_dict()
            file = request.files.get('comprovante')
            if file and file.filename:
                unique_name, orig_name, mime = save_upload(file)
                data['comprovante_path'] = unique_name
                data['comprovante_nome'] = orig_name
                data['comprovante_tipo'] = mime
        else:
            data = request.get_json(force=True) or {}

        if not imovel_belongs_to_user(data.get('imovel_id', ''), current_user.id):
            return jsonify({'error': 'Acesso negado'}), 403

        required = ['imovel_id', 'nicho', 'descricao', 'valor', 'data_pagamento', 'forma_pagamento']
        for field in required:
            if not data.get(field):
                return jsonify({'error': f'Campo obrigatorio: {field}'}), 400

        custo = add_custo(DB_PATH, data)
        return jsonify(custo), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/custos/<custo_id>', methods=['PUT'])
@login_required
def api_update_custo(custo_id):
    try:
        if not custo_belongs_to_user(custo_id, current_user.id):
            return jsonify({'error': 'Acesso negado'}), 403

        existing = get_custo(DB_PATH, custo_id)
        if not existing:
            return jsonify({'error': 'Custo nao encontrado'}), 404

        data = {}
        new_file_uploaded = False

        if request.content_type and 'multipart' in request.content_type:
            data = request.form.to_dict()
            file = request.files.get('comprovante')
            if file and file.filename:
                old_path = existing.get('comprovante_path')
                if old_path:
                    full_old = os.path.join(UPLOAD_FOLDER, old_path)
                    if os.path.exists(full_old):
                        os.remove(full_old)
                unique_name, orig_name, mime = save_upload(file)
                data['comprovante_path'] = unique_name
                data['comprovante_nome'] = orig_name
                data['comprovante_tipo'] = mime
                new_file_uploaded = True
        else:
            data = request.get_json(force=True) or {}

        if not new_file_uploaded:
            data['comprovante_path'] = None

        custo = update_custo(DB_PATH, custo_id, data)
        return jsonify(custo)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/custos/<custo_id>', methods=['DELETE'])
@login_required
def api_delete_custo(custo_id):
    try:
        if not custo_belongs_to_user(custo_id, current_user.id):
            return jsonify({'error': 'Acesso negado'}), 403
        comp_path = delete_custo(DB_PATH, custo_id)
        if comp_path:
            full_path = os.path.join(UPLOAD_FOLDER, comp_path)
            if os.path.exists(full_path):
                os.remove(full_path)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─── File serving ─────────────────────────────────────────────────────────────

@app.route('/uploads/<filename>')
@login_required
def serve_upload(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


# ─── Excel Export ─────────────────────────────────────────────────────────────

HEADER_FILL = PatternFill(start_color="0f172a", end_color="0f172a", fill_type="solid")
HEADER_FONT = Font(color="FFFFFF", bold=True, size=11)
SUBHEADER_FILL = PatternFill(start_color="6366f1", end_color="6366f1", fill_type="solid")
SUBHEADER_FONT = Font(color="FFFFFF", bold=True, size=10)
TOTAL_FILL = PatternFill(start_color="eef2ff", end_color="eef2ff", fill_type="solid")
TOTAL_FONT = Font(bold=True, size=11, color="0f172a")
ALT_FILL = PatternFill(start_color="f8fafc", end_color="f8fafc", fill_type="solid")

thin = Side(style='thin', color='e2e8f0')
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)

COLS = ['Data Pagamento', 'Nicho', 'Descricao', 'Favorecido', 'Forma Pagamento', 'Comprovante', 'Observacoes', 'Valor (R$)']
COL_WIDTHS = [18, 28, 38, 26, 22, 30, 36, 18]


def write_sheet(ws, imovel, custos):
    ws.merge_cells('A1:H1')
    title_cell = ws['A1']
    title_cell.value = f"Imovel: {imovel['nome']}"
    title_cell.font = Font(color="FFFFFF", bold=True, size=14)
    title_cell.fill = HEADER_FILL
    title_cell.alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[1].height = 28

    ws.merge_cells('A2:H2')
    addr_parts = []
    if imovel.get('rua'):
        addr_parts.append(imovel['rua'])
    if imovel.get('numero'):
        addr_parts.append(f"No {imovel['numero']}")
    if imovel.get('complemento'):
        addr_parts.append(imovel['complemento'])
    if imovel.get('cep'):
        addr_parts.append(f"CEP {imovel['cep']}")
    addr_cell = ws['A2']
    addr_cell.value = ', '.join(addr_parts) if addr_parts else 'Sem endereco'
    addr_cell.font = Font(color="FFFFFF", size=10)
    addr_cell.fill = PatternFill(start_color="1e293b", end_color="1e293b", fill_type="solid")
    addr_cell.alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[2].height = 18

    ws.merge_cells('A3:H3')
    arr_cell = ws['A3']
    arr_date = imovel.get('data_arrematacao', '')
    arr_cell.value = f"Data de Arrematacao: {arr_date}" if arr_date else ''
    arr_cell.font = Font(color="FFFFFF", size=9)
    arr_cell.fill = PatternFill(start_color="1e293b", end_color="1e293b", fill_type="solid")
    arr_cell.alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[3].height = 14

    for col_i, (col_name, col_w) in enumerate(zip(COLS, COL_WIDTHS), start=1):
        cell = ws.cell(row=5, column=col_i, value=col_name)
        cell.font = SUBHEADER_FONT
        cell.fill = SUBHEADER_FILL
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = BORDER
        ws.column_dimensions[get_column_letter(col_i)].width = col_w
    ws.row_dimensions[5].height = 20

    total = 0.0
    for row_i, c in enumerate(custos, start=6):
        fill = ALT_FILL if row_i % 2 == 0 else PatternFill(fill_type=None)
        vals = [
            c.get('data_pagamento', ''),
            c.get('nicho', ''),
            c.get('descricao', ''),
            c.get('favorecido', ''),
            c.get('forma_pagamento', ''),
            c.get('comprovante_nome', ''),
            c.get('observacoes', ''),
            c.get('valor', 0.0),
        ]
        for col_i, val in enumerate(vals, start=1):
            cell = ws.cell(row=row_i, column=col_i, value=val)
            cell.border = BORDER
            cell.fill = fill
            cell.alignment = Alignment(vertical='center', wrap_text=(col_i in [3, 7]))
            if col_i == 8:
                cell.number_format = '#,##0.00'
                cell.alignment = Alignment(horizontal='right', vertical='center')
        total += float(c.get('valor', 0))
        ws.row_dimensions[row_i].height = 16

    total_row = len(custos) + 6
    ws.merge_cells(f'A{total_row}:G{total_row}')
    label_cell = ws.cell(row=total_row, column=1, value='TOTAL INVESTIDO')
    label_cell.font = TOTAL_FONT
    label_cell.fill = TOTAL_FILL
    label_cell.alignment = Alignment(horizontal='right', vertical='center')
    label_cell.border = BORDER

    val_cell = ws.cell(row=total_row, column=8, value=total)
    val_cell.font = TOTAL_FONT
    val_cell.fill = TOTAL_FILL
    val_cell.number_format = '#,##0.00'
    val_cell.alignment = Alignment(horizontal='right', vertical='center')
    val_cell.border = BORDER
    ws.row_dimensions[total_row].height = 22

    nicho_totals = {}
    for c in custos:
        n = c.get('nicho', 'Outros')
        nicho_totals[n] = nicho_totals.get(n, 0) + float(c.get('valor', 0))

    summary_start = total_row + 2
    ws.cell(row=summary_start, column=1, value='Subtotal por Nicho').font = Font(bold=True, color='0f172a', size=10)
    ws.merge_cells(f'A{summary_start}:H{summary_start}')

    for si, (nicho, val) in enumerate(sorted(nicho_totals.items()), start=1):
        r = summary_start + si
        ws.cell(row=r, column=1, value=nicho).font = Font(bold=True)
        ws.cell(row=r, column=8, value=val).number_format = '#,##0.00'


@app.route('/api/export/excel/<imovel_id>')
@login_required
def export_excel(imovel_id):
    try:
        if not imovel_belongs_to_user(imovel_id, current_user.id):
            return jsonify({'error': 'Acesso negado'}), 403
        imoveis = get_imoveis(DB_PATH, current_user.id)
        imovel = next((i for i in imoveis if i['id'] == imovel_id), None)
        if not imovel:
            return jsonify({'error': 'Imovel nao encontrado'}), 404
        custos = get_custos(DB_PATH, imovel_id)
        wb = openpyxl.Workbook()
        ws = wb.active
        safe_name = ''.join(c for c in imovel['nome'] if c.isalnum() or c in (' ', '-', '_'))[:28]
        ws.title = safe_name or 'Imovel'
        write_sheet(ws, imovel, custos)
        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)
        fname = f"custos_{safe_name.replace(' ', '_')}.xlsx"
        return send_file(buf, as_attachment=True, download_name=fname,
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/export/excel/all')
@login_required
def export_excel_all():
    try:
        imoveis = get_imoveis(DB_PATH, current_user.id)
        if not imoveis:
            return jsonify({'error': 'Nenhum imovel cadastrado'}), 404

        wb = openpyxl.Workbook()
        wb.remove(wb.active)

        for imovel in imoveis:
            custos = get_custos(DB_PATH, imovel['id'])
            safe_name = ''.join(c for c in imovel['nome'] if c.isalnum() or c in (' ', '-', '_'))[:28]
            ws = wb.create_sheet(title=safe_name or f"Imovel_{imovel['id'][:6]}")
            write_sheet(ws, imovel, custos)

        ws_sum = wb.create_sheet(title='Resumo Geral', index=0)
        ws_sum.merge_cells('A1:C1')
        ws_sum['A1'].value = 'Resumo Geral — Todos os Imoveis'
        ws_sum['A1'].font = Font(color='FFFFFF', bold=True, size=14)
        ws_sum['A1'].fill = HEADER_FILL
        ws_sum['A1'].alignment = Alignment(horizontal='center', vertical='center')
        ws_sum.row_dimensions[1].height = 28

        headers = ['Imovel', 'Lancamentos', 'Total Investido (R$)']
        for ci, h in enumerate(headers, 1):
            cell = ws_sum.cell(row=3, column=ci, value=h)
            cell.font = SUBHEADER_FONT
            cell.fill = SUBHEADER_FILL
            cell.border = BORDER
            cell.alignment = Alignment(horizontal='center')

        ws_sum.column_dimensions['A'].width = 40
        ws_sum.column_dimensions['B'].width = 18
        ws_sum.column_dimensions['C'].width = 24

        grand_total = 0.0
        for ri, imovel in enumerate(imoveis, start=4):
            custos = get_custos(DB_PATH, imovel['id'])
            total = sum(float(c.get('valor', 0)) for c in custos)
            grand_total += total
            fill = ALT_FILL if ri % 2 == 0 else PatternFill(fill_type=None)
            c1 = ws_sum.cell(row=ri, column=1, value=imovel['nome'])
            c1.border = BORDER
            c1.fill = fill
            c2 = ws_sum.cell(row=ri, column=2, value=len(custos))
            c2.border = BORDER
            c2.fill = fill
            c2.alignment = Alignment(horizontal='center')
            c3 = ws_sum.cell(row=ri, column=3, value=total)
            c3.border = BORDER
            c3.fill = fill
            c3.number_format = '#,##0.00'
            c3.alignment = Alignment(horizontal='right')

        grand_row = len(imoveis) + 4
        ws_sum.merge_cells(f'A{grand_row}:B{grand_row}')
        gc1 = ws_sum.cell(row=grand_row, column=1, value='TOTAL GERAL')
        gc1.font = TOTAL_FONT
        gc1.fill = TOTAL_FILL
        gc1.border = BORDER
        gc1.alignment = Alignment(horizontal='right')
        gc3 = ws_sum.cell(row=grand_row, column=3, value=grand_total)
        gc3.font = TOTAL_FONT
        gc3.fill = TOTAL_FILL
        gc3.border = BORDER
        gc3.number_format = '#,##0.00'
        gc3.alignment = Alignment(horizontal='right')

        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)
        return send_file(buf, as_attachment=True, download_name='custos_arrematacao_todos.xlsx',
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    init_db(DB_PATH)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    port = int(os.environ.get('PORT', 5000))
    is_local = port == 5000
    if is_local:
        import webbrowser, threading
        threading.Timer(1.2, lambda: webbrowser.open('http://localhost:5000')).start()
    app.run(debug=False, host='0.0.0.0', port=port)
