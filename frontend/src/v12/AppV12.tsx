import { useCallback, useEffect, useState } from 'react';
import {
  ApiV12Error,
  EVENTO_PRECISA_API_KEY,
  ehErroApiKey,
  lerConfig,
  obterPesquisa,
  type ResearchRun,
} from '../services/apiV12';
import { ApiKeyGateV12 } from '../components/layout/ApiKeyGateV12';
import { HeroV12 } from '../components/layout/HeroV12';
import { MobileTabBarV12, useSidebarRecolhida } from '../components/layout/MobileTabBarV12';
import { NavbarV12 } from '../components/layout/NavbarV12';
import { SidebarV12, type RotaV12 } from '../components/layout/SidebarV12';
import {
  HistoryViewLocal,
  ResearchView,
  atualizarStatusHistorico,
  lerHistorico,
  registrarNoHistorico,
  type HistoricoItem,
} from './ResearchViews';
import {
  gravarIdAtivo,
  lerIdAtivo,
  limparIdAtivo,
  usePesquisaAoVivo,
} from './usePesquisaAoVivo';
import { useTemaV12 } from './useTemaV12';
import { SettingsView } from './SettingsV12';

function rotaDoHash(): RotaV12 {
  const h = window.location.hash.replace('#', '');
  if (h === 'history' || h === 'settings') return h;
  return 'research';
}

const TITULOS: Record<RotaV12, string> = {
  research: 'Pesquisa — Deep Research',
  history: 'Histórico — Deep Research',
  settings: 'Configuração — Deep Research',
};

export function AppV12() {
  const [rota, setRota] = useState<RotaV12>(() => rotaDoHash());
  // researchId vive no nível do app: trocar de rota não desmonta o stream.
  // Restaurado do localStorage para sobreviver ao reload.
  const [researchId, setResearchId] = useState<string | null>(() => lerIdAtivo());
  const [historico, setHistorico] = useState<HistoricoItem[]>(() => lerHistorico());
  const [erroAbrir, setErroAbrir] = useState<string | null>(null);
  const [precisaApiKey, setPrecisaApiKey] = useState(false);
  const [temaSugerido, setTemaSugerido] = useState<string | null>(null);
  // Força o hook a reabrir GET + SSE após salvar a chave (mesmo researchId).
  const [geracaoChave, setGeracaoChave] = useState(0);
  const [mostrarGate, setMostrarGate] = useState(false);
  const { tema, alternar } = useTemaV12();
  const { recolhida, alternar: alternarRecolher } = useSidebarRecolhida();

  // Hook no nível do app: GET único + SSE; trocar #history/#settings mantém o estado.
  const estado = usePesquisaAoVivo(researchId, geracaoChave);

  useEffect(() => {
    const onHash = () => setRota(rotaDoHash());
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  // Qualquer 401 do serviço sinaliza: mostra o aviso sem tocar na pesquisa ativa.
  useEffect(() => {
    const onPrecisa = () => setPrecisaApiKey(true);
    window.addEventListener(EVENTO_PRECISA_API_KEY, onPrecisa);
    return () => window.removeEventListener(EVENTO_PRECISA_API_KEY, onPrecisa);
  }, []);

  useEffect(() => {
    document.title = TITULOS[rota];
  }, [rota]);

  // Id obsoleto (404 do backend): limpa para voltar ao formulário.
  useEffect(() => {
    if (estado.naoEncontrada && researchId) {
      limparIdAtivo();
      setResearchId(null);
    }
  }, [estado.naoEncontrada, researchId]);

  const runStatus = estado.run?.status;
  const runId = estado.run?.research_id;
  // Mantém o histórico local em dia com o status do run.
  useEffect(() => {
    if (runId && runStatus) atualizarStatusHistorico(runId, runStatus);
  }, [runId, runStatus]);

  const recarregarHistorico = useCallback(() => setHistorico(lerHistorico()), []);

  const aoCriar = useCallback(
    (id: string) => {
      gravarIdAtivo(id);
      setResearchId(id);
      // Entrada no histórico aparece de imediato; status atualiza via efeito.
      try {
        obterPesquisa(id).then((run: ResearchRun) => {
          registrarNoHistorico(run);
          recarregarHistorico();
        });
      } catch {
        /* o hook já trata o erro */
      }
      recarregarHistorico();
    },
    [recarregarHistorico],
  );

  const aoNovaPesquisa = useCallback(() => {
    limparIdAtivo();
    setResearchId(null);
    setTemaSugerido(null);
    recarregarHistorico();
  }, [recarregarHistorico]);

  async function abrirPesquisa(id: string) {
    setErroAbrir(null);
    try {
      const run = await obterPesquisa(id);
      setPrecisaApiKey(false);
      gravarIdAtivo(id);
      setResearchId(id);
      registrarNoHistorico(run);
      recarregarHistorico();
      window.location.hash = '#research';
    } catch (e) {
      if (ehErroApiKey(e)) setPrecisaApiKey(true);
      setErroAbrir(e instanceof ApiV12Error ? e.message : 'Falha ao abrir pesquisa.');
    }
  }

  // Chave salva/testada no gate: refaz config, fecha aviso e retoma GET + SSE.
  const aoChaveValidada = useCallback(() => {
    setPrecisaApiKey(false);
    setMostrarGate(false);
    try {
      void lerConfig();
    } catch {
      /* o hook/SSE já sinaliza 401 de novo se falhar */
    }
    setGeracaoChave((g) => g + 1);
    if (researchId) {
      obterPesquisa(researchId).catch(() => {
        /* hook preserva estado parcial; erro já visível no painel */
      });
    }
  }, [researchId]);

  const navegar = useCallback((r: RotaV12) => {
    window.location.hash = `#${r}`;
    setRota(r);
  }, []);

  const heroAtivo = rota === 'research' && estado.researchId == null;
  const revelarGate = precisaApiKey || mostrarGate;

  return (
    <div className="app-shell">
      <SidebarV12
        rota={rota}
        navegar={navegar}
        novaPesquisa={aoNovaPesquisa}
        tema={tema}
        alternarTema={alternar}
        recolhida={recolhida}
        alternarRecolher={alternarRecolher}
        historico={historico}
        pesquisaAtivaId={researchId}
        abrirPesquisa={(id) => void abrirPesquisa(id)}
      />
      <main className="app-main">
        <NavbarV12
          rota={rota}
          navegar={navegar}
          novaPesquisa={aoNovaPesquisa}
          tema={tema}
          alternarTema={alternar}
        />
        <div className="workspace-main">
          <div className="v12-main">
            {revelarGate && (
              <div className="alert-banner danger" role="alert">
                API key inválida ou ausente.{' '}
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setMostrarGate((v) => !v)}
                  aria-expanded={mostrarGate}
                >
                  {mostrarGate ? 'Ocultar configuração' : 'Configurar API key'}
                </button>{' '}
                — a pesquisa ativa foi preservada.
              </div>
            )}
            {erroAbrir && (
              <div className="alert-banner danger" role="alert">
                {erroAbrir}
              </div>
            )}
            {rota === 'research' && (
              <>
                <ApiKeyGateV12 key={mostrarGate ? 'aberto' : 'estado'} aoValidar={aoChaveValidada} />
                {heroAtivo && <HeroV12 aoEscolher={(t) => setTemaSugerido(t)} />}
                <ResearchView
                  estado={estado}
                  aoCriar={aoCriar}
                  aoNovaPesquisa={aoNovaPesquisa}
                  temaSugerido={temaSugerido}
                />
              </>
            )}
            {rota === 'history' && (
              <HistoryViewLocal
                itens={historico}
                ativaId={researchId}
                onAbrir={(id) => void abrirPesquisa(id)}
                onRecarregar={recarregarHistorico}
              />
            )}
            {rota === 'settings' && <SettingsView />}
          </div>
        </div>
        <MobileTabBarV12 rota={rota} navegar={navegar} novaPesquisa={aoNovaPesquisa} />
      </main>
    </div>
  );
}
