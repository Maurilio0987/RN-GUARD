import sqlite3
from flask import g
import hashlib
import json


BANCO_DE_DADOS = 'bancodedados.db'

# Função para obter conexão com o banco
def obter_conexao():
    if '_database' not in g:
        g._database = sqlite3.connect(BANCO_DE_DADOS)
    return g._database

# Função para fechar a conexão com o banco
def fechar_conexao(e=None):
    db = g.pop('_database', None)
    if db is not None:
        db.close()

# Função para inicializar o banco de dados (criar as tabelas)
def inicializar_banco():
    db = obter_conexao()
    db.execute("drop table documentos")
    db.execute("drop table usuarios")
    db.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_usuario TEXT NOT NULL UNIQUE,
            cpf TEXT,
            senha TEXT NOT NULL,
            papel TEXT NOT NULL
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS documentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_arquivo TEXT NOT NULL,
            caminho_arquivo TEXT NOT NULL,
            hash TEXT NOT NULL,
            usuario_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pendente',
            categoria TEXT NOT NULL,
            aprovacoes TEXT,
            data_documento DATE NOT NULL,
            data_envio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        )
    ''')
    db.commit()

# Função para buscar um usuário pelo nome de usuário e senha
def obter_usuario_por_credenciais(nome_usuario, senha):
    db = obter_conexao()
    return db.execute('SELECT * FROM usuarios WHERE nome_usuario = ? AND senha = ?', (nome_usuario, senha)).fetchone()

# Função para inserir um novo usuário
def inserir_usuario(nome_usuario, senha, papel, cpf=None):
    db = obter_conexao()
    db.execute('INSERT INTO usuarios (nome_usuario, senha, papel, cpf) VALUES (?, ?, ?, ?)', (nome_usuario, senha, papel, cpf))
    db.commit()


# Função para obter todos os usuários
def obter_todos_usuarios():
    db = obter_conexao()
    return db.execute('SELECT id, nome_usuario, papel FROM usuarios').fetchall()

# Função para excluir um usuário pelo ID
def excluir_usuario_por_id(usuario_id):
    db = obter_conexao()
    db.execute('DELETE FROM usuarios WHERE id = ?', (usuario_id,))
    db.commit()

# Função para obter um documento por ID
def obter_documento_por_id(documento_id):
    db = obter_conexao()
    return db.execute('SELECT * FROM documentos WHERE id = ?', (documento_id,)).fetchone()

# Função para calcular hash de um arquivo
def calcular_hash_arquivo(caminho_arquivo):
    hash_sha256 = hashlib.sha256()
    with open(caminho_arquivo, 'rb') as f:
        for bloco in iter(lambda: f.read(4096), b""):
            hash_sha256.update(bloco)
    return hash_sha256.hexdigest()

# Função para hashear senha
def hash_senha(senha):
    return hashlib.sha256(senha.encode('utf-8')).hexdigest()

# NOVA: Função para salvar documento com os campos atualizados
def salvar_documento(nome_arquivo, caminho_arquivo, hash, usuario_id, categoria, data_documento, lista_aprovacoes):
    db = obter_conexao()

    # Converter a lista de aprovações para uma string JSON
    aprovacoes_json = json.dumps(lista_aprovacoes)

    # Inserir o documento no banco de dados, incluindo a lista de aprovações
    db.execute(''' 
        INSERT INTO documentos (nome_arquivo, caminho_arquivo, hash, usuario_id, categoria, data_documento, aprovacoes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (nome_arquivo, caminho_arquivo, hash, usuario_id, categoria, data_documento, aprovacoes_json))
    
    db.commit()

# Função para verificar se hash já existe
def hash_existe(hash_arquivo):
    db = obter_conexao()
    return db.execute("SELECT id FROM documentos WHERE hash = ?", (hash_arquivo,)).fetchone() is not None
