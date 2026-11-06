from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr, Field
import pymysql

app = FastAPI(
    title="API de Ciência de Dados",
    description="Aula 2: a mesma API, agora lendo e gravando num banco MySQL.",
    version="2.0.0",
)


class NovoAluno(BaseModel):
    nome: str = Field(min_length=2, max_length=100)
    email: EmailStr
    curso_id: int = Field(gt=0)
    ano_ingresso: int = Field(ge=2000, le=2099)


class NovaNota(BaseModel):
    aluno_id: int = Field(gt=0)
    disciplina_id: int = Field(gt=0)
    nota: float = Field(ge=0, le=10)


def conectar():
    return pymysql.connect(
        host="localhost",
        port=3306,
        user="root",
        password="ceub123456",
        database="escola",
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


@app.get("/")
def inicio():
    return {
        "mensagem": "Bem-vindos à API de Ciência de Dados!",
        "documentacao": "/docs",
    }


@app.get("/saude")
def saude():
    try:
        with conectar() as conexao:
            with conexao.cursor() as cursor:
                cursor.execute("SELECT DATABASE() AS banco, VERSION() AS versao")
                info = cursor.fetchone()
    except pymysql.err.OperationalError:
        raise HTTPException(
            status_code=503,
            detail="Não foi possível conectar ao banco de dados",
        )

    return {
        "status": "ok",
        "banco": info["banco"],
        "versao": info["versao"],
    }


@app.get("/sobre")
def sobre():
    return {
        "disciplina": "Programação para Ciência de Dados",
        "aula": 2,
        "versao_api": "2.0.0",
    }


@app.get("/alunos")
def listar_alunos(curso: str | None = None, ano: int | None = None):
    sql = """
        SELECT a.id, a.nome, a.email, a.ano_ingresso, c.sigla AS curso
        FROM alunos a
        JOIN cursos c ON c.id = a.curso_id
    """

    condicoes = []
    parametros = []

    if curso:
        condicoes.append("c.sigla = %s")
        parametros.append(curso)

    if ano:
        condicoes.append("a.ano_ingresso = %s")
        parametros.append(ano)

    if condicoes:
        sql += " WHERE " + " AND ".join(condicoes)

    sql += " ORDER BY a.id"

    try:
        with conectar() as conexao:
            with conexao.cursor() as cursor:
                cursor.execute(sql, parametros)
                alunos = cursor.fetchall()
    except pymysql.err.OperationalError:
        raise HTTPException(
            status_code=503,
            detail="Não foi possível conectar ao banco de dados",
        )

    return {
        "total": len(alunos),
        "alunos": alunos,
    }


@app.post("/alunos", status_code=201)
def cadastrar_aluno(novo_aluno: NovoAluno):
    sql = """
        INSERT INTO alunos (nome, email, curso_id, ano_ingresso)
        VALUES (%s, %s, %s, %s)
    """

    valores = (
        novo_aluno.nome,
        novo_aluno.email,
        novo_aluno.curso_id,
        novo_aluno.ano_ingresso,
    )

    try:
        with conectar() as conexao:
            with conexao.cursor() as cursor:
                cursor.execute(sql, valores)
                novo_id = cursor.lastrowid
                conexao.commit()
    except pymysql.err.IntegrityError as erro:
        codigo = erro.args[0]
        if codigo == 1062:
            raise HTTPException(
                status_code=409,
                detail="Já existe um aluno com este e-mail",
            )
        if codigo == 1452:
            raise HTTPException(
                status_code=422,
                detail="Curso não encontrado",
            )
        raise
    except pymysql.err.OperationalError:
        raise HTTPException(
            status_code=503,
            detail="Não foi possível conectar ao banco de dados",
        )

    return {
        "mensagem": "Aluno cadastrado com sucesso",
        "id": novo_id,
    }


@app.get("/alunos/{aluno_id}")
def consultar_aluno(aluno_id: int):
    sql = """
        SELECT a.id, a.nome, a.email, a.ano_ingresso, c.sigla AS curso
        FROM alunos a
        JOIN cursos c ON c.id = a.curso_id
        WHERE a.id = %s
    """
    try:
        with conectar() as conexao:
            with conexao.cursor() as cursor:
                cursor.execute(sql, (aluno_id,))
                aluno = cursor.fetchone()
    except pymysql.err.OperationalError:
        raise HTTPException(
            status_code=503,
            detail="Não foi possível conectar ao banco de dados",
        )

    if aluno is None:
        raise HTTPException(
            status_code=404,
            detail="Aluno não encontrado",
        )

    return aluno


@app.get("/alunos/{aluno_id}/notas")
def notas_do_aluno(aluno_id: int):
    try:
        with conectar() as conexao:
            with conexao.cursor() as cursor:
                cursor.execute(
                    "SELECT nome FROM alunos WHERE id = %s", (aluno_id,)
                )
                aluno = cursor.fetchone()

                if aluno is None:
                    raise HTTPException(
                        status_code=404,
                        detail="Aluno não encontrado",
                    )

                sql_notas = """
                    SELECT d.nome AS disciplina, n.nota
                    FROM notas n
                    JOIN disciplinas d ON d.id = n.disciplina_id
                    WHERE n.aluno_id = %s
                    ORDER BY d.nome
                """
                cursor.execute(sql_notas, (aluno_id,))
                notas = cursor.fetchall()
    except pymysql.err.OperationalError:
        raise HTTPException(
            status_code=503,
            detail="Não foi possível conectar ao banco de dados",
        )

    media = None
    if notas:
        media = round(sum(n["nota"] for n in notas) / len(notas), 2)

    return {
        "aluno": aluno["nome"],
        "quantidade": len(notas),
        "media": media,
        "notas": notas,
    }


@app.post("/notas", status_code=201)
def lancar_nota(nova_nota: NovaNota):
    sql = """
        INSERT INTO notas (aluno_id, disciplina_id, nota)
        VALUES (%s, %s, %s)
    """

    valores = (nova_nota.aluno_id, nova_nota.disciplina_id, nova_nota.nota)

    try:
        with conectar() as conexao:
            with conexao.cursor() as cursor:
                cursor.execute(sql, valores)
                conexao.commit()
    except pymysql.err.IntegrityError as erro:
        codigo = erro.args[0]
        if codigo == 1062:
            raise HTTPException(
                status_code=409,
                detail="Este aluno já tem nota nesta disciplina",
            )
        if codigo == 1452:
            raise HTTPException(
                status_code=422,
                detail="Aluno ou disciplina não encontrado",
            )
        raise
    except pymysql.err.OperationalError:
        raise HTTPException(
            status_code=503,
            detail="Não foi possível conectar ao banco de dados",
        )

    return {"mensagem": "Nota lançada com sucesso"}


@app.get("/indicadores")
def indicadores():
    sql = """
        SELECT
            COUNT(*)                             AS quantidade_notas,
            COUNT(DISTINCT aluno_id)             AS alunos_avaliados,
            ROUND(AVG(nota), 2)                  AS media_das_notas,
            MAX(nota)                            AS maior_nota,
            MIN(nota)                            AS menor_nota,
            SUM(CASE WHEN nota >= 7 THEN 1 ELSE 0 END) AS aprovacoes
        FROM notas
    """
    try:
        with conectar() as conexao:
            with conexao.cursor() as cursor:
                cursor.execute(sql)
                resultado = cursor.fetchone()
    except pymysql.err.OperationalError:
        raise HTTPException(
            status_code=503,
            detail="Não foi possível conectar ao banco de dados",
        )

    return resultado


@app.get("/indicadores/disciplinas")
def indicadores_por_disciplina():
    sql = """
        SELECT
            d.nome                                      AS disciplina,
            COUNT(*)                                    AS quantidade_notas,
            ROUND(AVG(n.nota), 2)                       AS media,
            SUM(CASE WHEN n.nota >= 7 THEN 1 ELSE 0 END) AS aprovacoes
        FROM notas n
        JOIN disciplinas d ON d.id = n.disciplina_id
        GROUP BY d.id, d.nome
        ORDER BY media DESC
    """
    try:
        with conectar() as conexao:
            with conexao.cursor() as cursor:
                cursor.execute(sql)
                disciplinas = cursor.fetchall()
    except pymysql.err.OperationalError:
        raise HTTPException(
            status_code=503,
            detail="Não foi possível conectar ao banco de dados",
        )

    return {"disciplinas": disciplinas}