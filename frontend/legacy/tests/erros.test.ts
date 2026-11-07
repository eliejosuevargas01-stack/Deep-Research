/**
 * Tradução de falhas para texto humano.
 *
 * Garante que nenhum aviso mostre jargão de transporte para a pessoa
 * (HTTP, backend, FastAPI, stack) e que o detalhe técnico continue disponível
 * em "Detalhes técnicos".
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { apresentarErro, resumirErro, statusDeErro } from '../utils/erros';
import { ApiError } from '../services/api';

const JARGAO = /\b(backend|FastAPI|HTTP|stack|traceback|ECONNREFUSED|500|502|504)\b/;

test('500 vira título humano e mantém o detalhe técnico', () => {
  const erro = new ApiError(500, 'Internal Server Error');
  const falha = apresentarErro(erro, { acao: 'abrir a sessão' });

  assert.equal(falha.titulo, 'O servidor travou no meio do caminho');
  assert.match(falha.mensagem, /Nada foi perdido/);
  assert.match(falha.detalhe ?? '', /HTTP 500/);
  assert.ok(!JARGAO.test(falha.titulo), 'título não pode ter jargão');
  assert.ok(!JARGAO.test(falha.mensagem), 'mensagem não pode ter jargão');
});

test('sessão expirada diz o que fazer e o que continua salvo', () => {
  const falha = apresentarErro(new ApiError(401, 'Unauthorized'), { acao: 'carregar as credenciais' });
  assert.equal(falha.titulo, 'Sua sessão expirou');
  assert.match(falha.mensagem, /continuam salvas/);
});

test('pesquisa ausente aponta o Histórico como saída', () => {
  const falha = apresentarErro(new ApiError(404, 'Not Found'), { acao: 'abrir a pesquisa' });
  assert.equal(falha.titulo, 'Não encontramos essa pesquisa');
  assert.match(falha.mensagem, /Histórico/);
});

test('excesso de tentativas pede espera curta', () => {
  const falha = apresentarErro(new ApiError(429, 'Too Many Requests'), { acao: 'enviar o tema' });
  assert.equal(falha.titulo, 'Muitas tentativas em pouco tempo');
  assert.match(falha.mensagem, /um minuto/);
});

test('rede fora reconhece erro de fetch', () => {
  const falha = apresentarErro(new TypeError('Failed to fetch'), { acao: 'salvar a credencial' });
  assert.equal(falha.titulo, 'Sem conexão com o servidor');
  assert.equal(statusDeErro(new TypeError('Failed to fetch')), 0);
});

test('timeout e erro de provedor têm textos próprios', () => {
  const timeout = apresentarErro(new Error('upstream request timeout after 60s'), { acao: 'redigir o dossiê' });
  assert.equal(timeout.titulo, 'A resposta demorou demais');

  const provedor = apresentarErro(new Error('LLM_PROVIDER_ERROR: 429 do provedor'), { acao: 'buscar evidências' });
  assert.equal(provedor.titulo, 'O provedor de IA não respondeu');
});

test('fallback nomeia a ação que falhou', () => {
  const falha = apresentarErro(new Error('algo estranho'), { acao: 'salvar a credencial' });
  assert.equal(falha.titulo, 'Não foi possível salvar a credencial');
  assert.match(falha.mensagem, /Tente de novo/);
  assert.equal(falha.detalhe, 'algo estranho');
});

test('erro vazio ainda produz aviso utilizável', () => {
  const falha = apresentarErro(undefined, { acao: 'carregar as fontes' });
  assert.ok(falha.titulo.length > 0);
  assert.ok(falha.mensagem.length > 0);
});

test('tom de aviso é preservado', () => {
  const falha = apresentarErro(new Error('Conexão de streaming interrompida após múltiplas tentativas.'), {
    acao: 'acompanhar a pesquisa ao vivo',
    tom: 'aviso',
  });
  assert.equal(falha.tom, 'aviso');
  assert.equal(falha.titulo, 'Não foi possível acompanhar a pesquisa ao vivo');
});

test('resumo junta título e mensagem em uma linha', () => {
  const resumo = resumirErro(new ApiError(503, 'Service Unavailable'), { acao: 'consultar o andamento' });
  assert.equal(resumo, 'O serviço está fora do ar. Costuma voltar em minutos. Tente de novo daqui a pouco.');
});
