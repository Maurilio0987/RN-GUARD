from flask import Flask, render_template, request, redirect, url_for, session, flash, current_app, send_file
import json
import db
import os
from functools import wraps
import uuid
from werkzeug.utils import secure_filename
import sqlite3
import re


categorias = [
        'Receitas',
        'Despesas',
        'Relatórios Contábeis',
        'Orçamento do Município',
        'Licitações e Contratos'
    ]

app = Flask(__name__)
app.secret_key = 'segredo123'
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def validar_cpf(cpf):
    # Remove qualquer caracter não numérico (pontos, traços)
    cpf = re.sub(r'\D', '', cpf)
    
    # Verifica se o CPF tem exatamente 11 dígitos
    if len(cpf) != 11 or not cpf.isdigit():
        return False
    
    # Lógica de validação do CPF (módulo 11)
    if cpf == cpf[0] * 11:  # CPF com todos os números iguais é inválido
        return False
    
    # Validação do primeiro dígito
    soma = 0
    for i in range(9):
        soma += int(cpf[i]) * (10 - i)
    resto = soma % 11
    if resto < 2:
        digito1 = 0
    else:
        digito1 = 11 - resto
    if int(cpf[9]) != digito1:
        return False

    # Validação do segundo dígito
    soma = 0
    for i in range(10):
        soma += int(cpf[i]) * (11 - i)
    resto = soma % 11
    if resto < 2:
        digito2 = 0
    else:
        digito2 = 11 - resto
    if int(cpf[10]) != digito2:
        return False

    return True



@app.before_request
def before_request():
    db.obter_conexao()

@app.teardown_appcontext
def teardown_db(exception):
    db.fechar_conexao(exception)

@app.route('/')
def index():
    return render_template('index.html', categorias=categorias)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        nome_usuario = request.form['nome_usuario']
        senha = request.form['senha']
        usuario = db.obter_usuario_por_credenciais(nome_usuario, db.hash_senha(senha))
        if usuario:
            session['usuario_id'] = usuario[0]
            session['nome_usuario'] = usuario[1]
            session['papel'] = usuario[4]
            return redirect('/dashboard')
        else:
            flash('Login inválido. Por favor, tente novamente.', 'erro')
            return redirect('/login')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Você saiu da conta com sucesso.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'usuario_id' not in session:
        flash('Você precisa estar logado para acessar o painel.', 'danger')
        return redirect(url_for('login'))

    papel = session['papel']
    print(papel)
    if papel == 'admin':
        return redirect(url_for('dashboard_admin'))
    elif papel == 'auditor':
        return redirect(url_for('dashboard_auditor'))
    else:
        flash('Você não tem permissão para acessar o painel.', 'danger')
        return redirect(url_for('login'))

@app.route('/dashboard/admin')
def dashboard_admin():
    if 'usuario_id' not in session or session.get('papel') != 'admin':
        flash('Acesso restrito. Somente administradores podem acessar esta página.', 'danger')
        return redirect(url_for('login'))
    return render_template('dashboard_admin.html')


@app.route('/dashboard/auditor')
def dashboard_auditor():
    if 'usuario_id' not in session or session.get('papel') != 'auditor':
        flash('Acesso restrito. Somente auditores podem acessar esta página.', 'danger')
        return redirect(url_for('login'))
    return render_template('dashboard_auditor.html')


@app.route('/dashboard/admin/cadastrar_conta', methods=["GET", "POST"])
def cadastrar_conta():
    if session.get('papel') != 'admin':
        return 'Acesso negado', 403

    if request.method == 'POST':
        nome_usuario = request.form['nome_usuario']
        senha = request.form['senha']
        confirmar_senha = request.form['confirmar_senha']
        cpf = 0
        papel = request.form['papel']
        if papel != "admin":
            cpf = request.form['cpf']
        # Se o papel for "admin", o CPF não é obrigatório
        if papel != 'admin' and not validar_cpf(cpf):
            flash('CPF inválido. Por favor, insira um CPF válido.', 'danger')
            return render_template('cadastrar_conta.html')

        # Validação da confirmação da senha
        if senha != confirmar_senha:
            flash('As senhas não coincidem. Por favor, confirme a senha corretamente.', 'danger')
            return render_template('cadastrar_conta.html')

        # Hash da senha
        senha_hash = db.hash_senha(senha)

        try:
            # Inserir o usuário no banco de dados
            db.inserir_usuario(nome_usuario, senha_hash, papel, cpf if papel != 'admin' else None)
            flash('Usuário cadastrado com sucesso!', 'success')
        except Exception as e:
            flash(f'Erro: {str(e)}', 'danger')

    # Obtendo os usuários para exibição
    usuarios = db.obter_todos_usuarios()
    return render_template('cadastrar_conta.html', usuarios=usuarios)


@app.route('/excluir_usuario/<int:usuario_id>')
def excluir_usuario(usuario_id):
    if session.get('papel') != 'admin':
        flash('Acesso negado. Apenas administradores podem excluir usuários.', 'danger')
        return redirect(url_for('dashboard_admin'))

    db.excluir_usuario_por_id(usuario_id)
    flash('Usuário excluído com sucesso!', 'success')
    return redirect(url_for('cadastrar_conta'))


@app.route('/dashboard/auditor/enviar_documento', methods=["GET", "POST"])
def enviar_documento():
    if 'usuario_id' not in session or session.get('papel') != 'auditor':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('login'))

    if request.method == "POST":
        if 'arquivo' not in request.files:
            flash('Nenhum arquivo selecionado.', 'warning')
            return redirect(url_for('dashboard_auditor'))

        arquivo = request.files['arquivo']

        if arquivo.filename == '':
            flash('Nome de arquivo inválido.', 'warning')
            return redirect(url_for('dashboard_auditor'))

        data_documento = request.form.get('data_documento')
        categoria = request.form.get('categoria')
        nome_personalizado = request.form.get('nome_personalizado', '').strip()

        if not data_documento or not categoria:
            flash('Categoria e data do documento são obrigatórios.', 'warning')
            return redirect(url_for('enviar_documento'))

        pasta_upload = os.path.join(current_app.root_path, 'documentos')
        os.makedirs(pasta_upload, exist_ok=True)

        nome_original = secure_filename(arquivo.filename)
        extensao = os.path.splitext(nome_original)[1]
        nome_aleatorio = f"{uuid.uuid4().hex}{extensao}"
        caminho = os.path.join(pasta_upload, nome_aleatorio)
        arquivo.save(caminho)

        hash_arquivo = db.calcular_hash_arquivo(caminho)

        if db.hash_existe(hash_arquivo):
            os.remove(caminho)
            flash('Este documento já foi enviado anteriormente.', 'warning')
            return redirect(url_for('enviar_documento'))

        usuario_id = session.get('usuario_id')

        # Definir nome para salvar com extensão correta
        if nome_personalizado:
            if not os.path.splitext(nome_personalizado)[1]:
                nome_personalizado += extensao
            nome_para_salvar = secure_filename(nome_personalizado)
        else:
            nome_para_salvar = nome_original

        # Adicionar o id do usuário na lista de aprovações
        lista_aprovacoes = [usuario_id]

        # Salvar o documento no banco de dados, incluindo a lista de aprovações
        db.salvar_documento(
            nome_para_salvar,
            caminho,
            hash_arquivo,
            usuario_id,
            categoria,
            data_documento,
            lista_aprovacoes  # Passar a lista de aprovações aqui
        )

        flash('Arquivo enviado com sucesso!', 'success')
        return redirect(url_for('enviar_documento'))

    return render_template('enviar_documento.html')




@app.route('/documentos/<categoria>')
def visualizar_documentos_categoria(categoria):
    conn = sqlite3.connect('bancodedados.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome_arquivo, categoria, data_documento, data_envio, status, aprovacoes FROM documentos WHERE categoria = ?", (categoria,))
    rows = cursor.fetchall()
    conn.close()

    documentos = []
    for row in rows:
        documentos.append({
            'id': row[0],
            'nome_arquivo': row[1],
            'categoria': row[2],
            'data_documento': row[3],
            'data_envio': row[4],
            'status': row[5],
            'aprovacoes': list(map(int, json.loads(row[6]))) if row[6] else []
        })
        
    return render_template('documentos.html', documentos=documentos)


@app.route('/documentos/download/<int:doc_id>')
def baixar_documento(doc_id):
    conn = sqlite3.connect('bancodedados.db')
    cursor = conn.cursor()
    cursor.execute("SELECT caminho_arquivo, nome_arquivo FROM documentos WHERE id = ?", (doc_id,))
    result = cursor.fetchone()
    conn.close()

    if result:
        caminho, nome = result
        return send_file(caminho, as_attachment=True, download_name=nome)
    else:
        flash("Documento não encontrado.", "error")
        return redirect(url_for('visualizar_documentos'))

@app.route('/comparar_documento', methods=['GET', 'POST'])
def comparar_documento():
    if request.method == 'POST':
        if 'arquivo' not in request.files:
            flash('Nenhum arquivo enviado!', 'danger')
            return redirect(request.url)

        arquivo = request.files['arquivo']
        if arquivo.filename == '':
            flash('Nenhum arquivo selecionado!', 'warning')
            return redirect(request.url)

        caminho = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(arquivo.filename))
        arquivo.save(caminho)

        hash_doc = db.calcular_hash_arquivo(caminho)
        existe = db.hash_existe(hash_doc)

        if existe:
            flash('✅ Documento validado: existe no sistema e é considerado legítimo.', 'success')
        else:
            flash('⚠ Documento não encontrado no sistema. Pode ser desconhecido ou potencialmente fraudado.', 'warning')


        os.remove(caminho)  # remove arquivo temporário após verificação
        return redirect(url_for('comparar_documento'))

    return render_template('comparar_documento.html')

@app.route('/dashboard/auditor/validar_documento')
def validar_documento():
    return render_template('validar_documentos.html', categorias=categorias)

@app.route('/dashboard/auditor/validar_documentos/<categoria>')
def validar_documentos_categoria(categoria):
    conn = sqlite3.connect('bancodedados.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome_arquivo, categoria, data_documento, data_envio, status, aprovacoes FROM documentos WHERE categoria = ? AND status = 'Pendente'", (categoria,))
    rows = cursor.fetchall()
    conn.close()
    documentos = []
    for row in rows:
        documentos.append({
            'id': row[0],
            'nome_arquivo': row[1],
            'categoria': row[2],
            'data_documento': row[3],
            'data_envio': row[4],
            'status': row[5],
            'aprovacoes': list(map(int, json.loads(row[6]))) if row[6] else []
        })

    return render_template('documentos_validar.html', documentos=documentos, user_id=session["usuario_id"])


@app.route('/aprovar_documento/<int:doc_id>', methods=['POST'])
def aprovar_documento(doc_id):
    user_id = session["usuario_id"]
    if not user_id:
        flash('Usuário não autenticado.', 'error')
        return redirect(request.referrer)

    conn = sqlite3.connect('bancodedados.db')
    cursor = conn.cursor()

    # Pega aprovações atuais
    cursor.execute("SELECT aprovacoes FROM documentos WHERE id = ?", (doc_id,))
    result = cursor.fetchone()
    if not result:
        flash('Documento não encontrado.', 'error')
        return redirect(request.referrer)

    aprovacoes = json.loads(result[0]) if result[0] else []
    print(aprovacoes)
    if user_id in aprovacoes:
        flash('Você já aprovou este documento.', 'info')
        return redirect(request.referrer)

    aprovacoes.append(user_id)
    status = "Validado" if len(aprovacoes) >= 5 else "Pendente"

    # Atualiza no banco
    cursor.execute("UPDATE documentos SET aprovacoes = ?, status = ? WHERE id = ?",
                   (json.dumps(aprovacoes), status, doc_id))
    conn.commit()
    conn.close()

    flash('Documento aprovado com sucesso.', 'success')
    return redirect(request.referrer)


if __name__ == '__main__':
    with app.app_context():
        db.inicializar_banco()
    app.run(debug=True, host="0.0.0.0", port=8000)
