import streamlit as st
import graphviz
import time

st.set_page_config(page_title="Simulador PDA/NPDA", layout="wide", page_icon="🧠")

# ─────────────────────────────────────────────
#  ESTILO GLOBAL
# ─────────────────────────────────────────────
st.markdown("""
<style>
  .stButton>button { width: 100%; border-radius: 8px; font-weight: 600; }
  code { font-size: 0.85rem; }
  .block-container { padding-top: 1.5rem; }
  .stSelectbox label { font-weight: 600; }
    audio {
        display:none;
    }

</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  CONSTANTES
# ─────────────────────────────────────────────
EMPTY = {"ε", "λ", ""}          # notações aceitas para vazio / ε-transição
BOTTOM = "Z"                     # marcador de fundo da pilha


# ══════════════════════════════════════════════
#  CLASSE PDA  (determinístico)
# ══════════════════════════════════════════════
class PDA:
    """
    Autômato de Pilha Determinístico.
    Transições: dict { (estado, símbolo|ε, topo) -> (novo_estado, push_str|ε) }
    Aceita por estado final com pilha contendo apenas Z (ou vazia).
    """

    def __init__(self, states, initial, finals, transitions, description=""):
        self.states      = states
        self.initial     = initial
        self.finals      = finals
        self.transitions = transitions
        self.description = description
        self.reset()

    # ── reinicia para nova simulação ──────────
    def reset(self):
        self.state    = self.initial
        self.stack    = [BOTTOM]
        self.pos      = 0
        self.message  = ""
        self.accepted = False
        self.history  = []          # lista de IDs (estado, entrada_restante, pilha)

    # ── executa 1 passo ───────────────────────
    def step(self, entrada):
        if self.state in ("reject", "dead"):
            return False

        topo   = self.stack[-1] if self.stack else "ε"
        symbol = entrada[self.pos] if self.pos < len(entrada) else "ε"

        # Escolhe chave de transição: símbolo real → ε → λ
        key, is_eps = self._find_key(self.state, symbol, topo)
        if key is None:
            self.state   = "dead"
            self.message = (
                f"❌  Sem transição para "
                f"({symbol if symbol not in EMPTY else 'fim'}, topo={topo})"
            )
            return False

        new_state, push = self.transitions[key]

        # Desempilha topo
        if self.stack:
            self.stack.pop()

        # Empilha (da direita para esquerda para manter a ordem)
        if push not in EMPTY:
            for ch in reversed(push):
                self.stack.append(ch)

        # Avança fita só se consumiu símbolo real
        if not is_eps and symbol not in EMPTY:
            self.pos += 1

        # Grava histórico
        rest  = entrada[self.pos:] if self.pos < len(entrada) else "ε"
        pilha = "".join(reversed(self.stack)) if self.stack else "ε"
        self.history.append({
            "de": self.state,
            "para": new_state,
            "leu": key[1],
            "topo": topo,
            "push": push,
            "rest": rest,
            "pilha": pilha,
        })

        self.message = (
            f"**{self.state}** →({key[1]}, {topo}→{push})→ **{new_state}**"
        )
        self.state = new_state

        # Verifica aceitação
        if self.state in self.finals and self.pos >= len(entrada):
            self.accepted = True

        return True

    # ── acha a chave certa (prioridade: símbolo > ε > λ) ──
    def _find_key(self, state, symbol, topo):
        for s in ([symbol] if symbol not in EMPTY else []) + ["ε", "λ"]:
            k = (state, s, topo)
            if k in self.transitions:
                return k, (s in EMPTY)
        return None, False


# ══════════════════════════════════════════════
#  CLASSE NPDA  (não-determinístico)
# ══════════════════════════════════════════════
class NPDA:
    """
    Autômato de Pilha Não-Determinístico.
    Transições: dict { (estado, símbolo|ε, topo) -> [(novo_estado, push_str|ε), ...] }
    Mantém TODAS as configurações ativas em paralelo (simulação BFS).
    """

    def __init__(self, states, initial, finals, transitions, description=""):
        self.states      = states
        self.initial     = initial
        self.finals      = finals
        self.transitions = transitions
        self.description = description
        self.reset()

    def reset(self):
        self.configs  = [{"estado": self.initial, "pilha": [BOTTOM], "pos": 0}]
        self.message  = ""
        self.accepted = False
        self.history  = []

    def step(self, entrada):
        novos     = []
        mensagens = []

        for cfg in self.configs:
            state, stack, pos = cfg["estado"], cfg["pilha"], cfg["pos"]
            topo   = stack[-1] if stack else "ε"
            symbol = entrada[pos] if pos < len(entrada) else "ε"

            # Gera chaves a testar: símbolo real + ε + λ
            keys_to_try = []
            if symbol not in EMPTY:
                keys_to_try.append((state, symbol, topo))
            keys_to_try += [(state, "ε", topo), (state, "λ", topo)]

            for key in keys_to_try:
                if key not in self.transitions:
                    continue
                for (ns, push) in self.transitions[key]:
                    new_stack = stack.copy()
                    if new_stack:
                        new_stack.pop()
                    if push not in EMPTY:
                        for ch in reversed(push):
                            new_stack.append(ch)

                    new_pos = pos + (0 if key[1] in EMPTY else 1)
                    novos.append({"estado": ns, "pilha": new_stack, "pos": new_pos})

                    rest  = entrada[new_pos:] if new_pos < len(entrada) else "ε"
                    pilha = "".join(reversed(new_stack)) if new_stack else "ε"
                    mensagens.append({
                        "de": state, "para": ns,
                        "leu": key[1], "topo": topo, "push": push,
                        "rest": rest, "pilha": pilha,
                    })

        # Deduplica configurações
        seen, unique = set(), []
        for c in novos:
            k = (c["estado"], tuple(c["pilha"]), c["pos"])
            if k not in seen:
                seen.add(k)
                unique.append(c)

        self.configs = unique
        self.history.extend(mensagens)
        self.message = (
            "\n".join(f"[{m['de']}→{m['para']}] leu={m['leu']} push={m['push']}"
                      for m in mensagens)
            if mensagens else "❌  Todos os ramos morreram"
        )

        for c in self.configs:
            if c["estado"] in self.finals and c["pos"] >= len(entrada):
                self.accepted = True

        return len(self.configs) > 0


# ══════════════════════════════════════════════
#  DEFINIÇÃO DOS 4 AUTÔMATOS  (canônicos GfG / Sipser)
# ══════════════════════════════════════════════
def build_automata():
    return {

        # ──────────────────────────────────────────────
        # PDA 1 – L = { aⁿbⁿ | n ≥ 1 }
        #   Referência: GeeksforGeeks / Sipser Ex 2.14
        #   Estados: q0 (início) → q1 (empilha a) → q2 (desempilha b) → q3 (aceita)
        # ──────────────────────────────────────────────
        "PDA 1 — aⁿbⁿ (n ≥ 1)": PDA(
            states={"q0", "q1", "q2", "q3"},
            initial="q0",
            finals={"q3"},
            description=(
                "**L = { aⁿbⁿ | n ≥ 1 }**  \n"
                "Para cada `a` lido, empilha `A`. "
                "Ao encontrar o primeiro `b`, troca de fase e desempilha `A` para cada `b`. "
                "Aceita se a pilha fica com apenas `Z` ao final."
            ),
            transitions={
                # q0: empilha primeiro 'a' e vai para q1
                ("q0", "a", BOTTOM): ("q1", "A" + BOTTOM),

                # q1: continua empilhando 'a'
                ("q1", "a", "A"):    ("q1", "AA"),

                # q1 → q2: primeiro 'b' lido, desempilha um A
                ("q1", "b", "A"):    ("q2", "ε"),

                # q2: continua desempilhando com 'b'
                ("q2", "b", "A"):    ("q2", "ε"),

                # q2 → q3: pilha voltou ao fundo, aceita
                ("q2", "ε", BOTTOM): ("q3", BOTTOM),
            },
        ),

        # ──────────────────────────────────────────────
        # PDA 2 – Parênteses balanceados  L = { w ∈ {(,)}* | balanceados }
        #   Referência: GeeksforGeeks "Balanced Parentheses PDA"
        #   Estados: q0 (lendo) → q1 (aceita)
        # ──────────────────────────────────────────────
        "PDA 2 — Parênteses balanceados": PDA(
            states={"q0", "q1"},
            initial="q0",
            finals={"q1"},
            description=(
                "**L = { w ∈ {(,)}\\* | w tem parênteses balanceados }**  \n"
                "Empilha `X` para cada `(`. Remove `X` para cada `)`. "
                "Aceita via ε-transição quando a pilha retorna ao fundo `Z`."
            ),
            transitions={
                # Empilha '(' como X
                ("q0", "(", BOTTOM): ("q0", "X" + BOTTOM),
                ("q0", "(", "X"):    ("q0", "XX"),

                # Desempilha X para ')'
                ("q0", ")", "X"):    ("q0", "ε"),

                # Pilha vazia (só Z) e entrada acabou → aceita
                ("q0", "ε", BOTTOM): ("q1", BOTTOM),
            },
        ),

        # ──────────────────────────────────────────────
        # NPDA 1 – Palíndromos sobre {a,b}  L = { w | w = wᴿ }
        #   Referência: GeeksforGeeks "Palindrome PDA" / Sipser Ex 2.16
        #   O NPDA "adivinha" o centro via ε-transição (não-determinismo essencial)
        # ──────────────────────────────────────────────
        "NPDA 1 — Palíndromo wwᴿ": NPDA(
            states={"q0", "q1", "q2"},
            initial="q0",
            finals={"q2"},
            description=(
                "**L = { w ∈ {a,b}\\* | w = wᴿ }** (palíndromos de qualquer comprimento)  \n"
                "**q0** empilha cada símbolo lido.  \n"
                "Via **ε-transição** (não-determinismo), o NPDA 'chuta' que chegou na metade "
                "e passa para **q1**, onde desempilha comparando com a segunda metade.  \n"
                "Aceita quando a pilha chega ao `Z` e a entrada acabou."
            ),
            transitions={
                # q0: empilha tudo que lê
                ("q0", "a", BOTTOM): [("q0", "a" + BOTTOM)],
                ("q0", "b", BOTTOM): [("q0", "b" + BOTTOM)],
                ("q0", "a", "a"):    [("q0", "aa")],
                ("q0", "a", "b"):    [("q0", "ab")],
                ("q0", "b", "a"):    [("q0", "ba")],
                ("q0", "b", "b"):    [("q0", "bb")],

                # Não-determinismo: a qualquer momento pode ir para q1 (adivinhar o meio)
                ("q0", "ε", BOTTOM): [("q1", BOTTOM)],
                ("q0", "ε", "a"):    [("q1", "a")],
                ("q0", "ε", "b"):    [("q1", "b")],

                # Para palíndromos ímpares: pode também consumir símbolo central e ir para q1
                ("q0", "a", BOTTOM): [("q0", "a" + BOTTOM), ("q1", BOTTOM)],
                ("q0", "b", BOTTOM): [("q0", "b" + BOTTOM), ("q1", BOTTOM)],
                ("q0", "a", "a"):    [("q0", "aa"), ("q1", "a")],
                ("q0", "a", "b"):    [("q0", "ab"), ("q1", "b")],
                ("q0", "b", "a"):    [("q0", "ba"), ("q1", "a")],
                ("q0", "b", "b"):    [("q0", "bb"), ("q1", "b")],

                # q1: verifica espelho desempilhando
                ("q1", "a", "a"):    [("q1", "ε")],
                ("q1", "b", "b"):    [("q1", "ε")],

                # Aceita quando pilha vazia (só Z) e entrada acabou
                ("q1", "ε", BOTTOM): [("q2", BOTTOM)],
            },
        ),

        # ──────────────────────────────────────────────
        # NPDA 2 – L = { aⁿbⁿcᵐ | m,n ≥ 1 } ∪ { aⁿbᵐcᵐ | m,n ≥ 1 }
        #   Referência: GeeksforGeeks "NPDA for aⁿbⁿcᵐ | aⁿbᵐcᵐ"
        #   O NPDA ramifica logo no início: testa cada condição em paralelo
        # ──────────────────────────────────────────────
        "NPDA 2 — aⁿbⁿcᵐ ∪ aⁿbᵐcᵐ": NPDA(
            states={"q0", "q1", "q2", "q3", "q4", "q5", "q6", "qf"},
            initial="q0",
            finals={"qf"},
            description=(
                "**L = { aⁿbⁿcᵐ | m,n ≥ 1 } ∪ { aⁿbᵐcᵐ | m,n ≥ 1 }**  \n"
                "Via **ε-transição** em q0, o NPDA ramifica em dois caminhos:  \n"
                "- **Ramo 1** (q1→q2→q3): verifica se #a = #b, ignora c's  \n"
                "- **Ramo 2** (q4→q5→q6): ignora a's, verifica se #b = #c  \n"
                "Aceita se **qualquer** ramo chegar ao estado final `qf`."
            ),
            transitions={
                # ── Bifurcação inicial (não-determinismo) ──
                ("q0", "ε", BOTTOM): [("q1", BOTTOM), ("q4", BOTTOM)],

                # ══ RAMO 1: testa #a = #b ══
                # q1: empilha A para cada 'a'
                ("q1", "a", BOTTOM): [("q1", "A" + BOTTOM)],
                ("q1", "a", "A"):    [("q1", "AA")],
                # q1 → q2: primeiro 'b' → começa a desempilhar
                ("q1", "b", "A"):    [("q2", "ε")],
                # q2: continua desempilhando A com 'b'
                ("q2", "b", "A"):    [("q2", "ε")],
                # q2 → q3: pilha voltou ao fundo; agora lê c's livremente
                ("q2", "ε", BOTTOM): [("q3", BOTTOM)],
                # q3: consome c's (m ≥ 1 obrigatório, então primeiro 'c' vai para qf)
                ("q3", "c", BOTTOM): [("q3", BOTTOM)],
                # q3 → aceita: entrada acabou, só resta Z
                ("q3", "ε", BOTTOM): [("qf", BOTTOM)],

                # ══ RAMO 2: testa #b = #c ══
                # q4: ignora todos os 'a's
                ("q4", "a", BOTTOM): [("q4", BOTTOM)],
                # q4 → q5: ε-transição para fase de empilhar 'b'
                ("q4", "ε", BOTTOM): [("q5", BOTTOM)],
                # q5: empilha B para cada 'b'
                ("q5", "b", BOTTOM): [("q5", "B" + BOTTOM)],
                ("q5", "b", "B"):    [("q5", "BB")],
                # q5 → q6: primeiro 'c' → desempilha B
                ("q5", "c", "B"):    [("q6", "ε")],
                # q6: continua desempilhando B com 'c'
                ("q6", "c", "B"):    [("q6", "ε")],
                # q6 → aceita: pilha voltou ao fundo e entrada acabou
                ("q6", "ε", BOTTOM): [("qf", BOTTOM)],
            },
        ),
    }


# ══════════════════════════════════════════════
#  GRÁFICO GRAPHVIZ
# ══════════════════════════════════════════════
def draw_graph(automato, active_states=None):
    dot = graphviz.Digraph()
    dot.attr(rankdir="LR", bgcolor="transparent")
    dot.attr("node", fontname="Helvetica", fontsize="12")

    active_states = set(active_states or [])

    for s in automato.states:
        shape = "doublecircle" if s in automato.finals else "circle"
        if s in active_states:
            dot.node(s, s, shape=shape,
                     style="filled", fillcolor="#3B82F6", fontcolor="white",
                     color="#1D4ED8", penwidth="2.5")
        elif s == automato.initial:
            dot.node(s, s, shape=shape,
                     style="filled", fillcolor="#10B981", fontcolor="white",
                     color="#047857", penwidth="2")
        else:
            dot.node(s, s, shape=shape, color="#6B7280")

    # Seta de entrada no estado inicial
    dot.node("__start__", "", shape="none", width="0")
    dot.edge("__start__", automato.initial)

    if isinstance(automato, PDA):
        for (s, sym, top), (ns, push) in automato.transitions.items():
            dot.edge(s, ns, label=f" {sym},{top}→{push} ",
                     fontsize="10", fontcolor="#374151")
    else:
        for (s, sym, top), targets in automato.transitions.items():
            for (ns, push) in targets:
                dot.edge(s, ns, label=f" {sym},{top}→{push} ",
                         fontsize="10", fontcolor="#374151")

    return dot


# ══════════════════════════════════════════════
#  TABELA DE HISTÓRICO
# ══════════════════════════════════════════════
def render_history_table(history):
    if not history:
        return
    rows = []
    for i, h in enumerate(history, 1):
        rows.append(
            f"| {i} | `{h['de']}` | `{h['leu']}` | `{h['topo']}` "
            f"| `{h['push']}` | `{h['para']}` | `{h['rest']}` | `{h['pilha']}` |"
        )
    header = (
        "| # | De | Leu | Topo | Push | Para | Restante | Pilha |\n"
        "|---|----|----|------|------|------|----------|-------|"
    )
    st.markdown(header + "\n" + "\n".join(rows))


# ══════════════════════════════════════════════
#  INTERFACE PRINCIPAL
# ══════════════════════════════════════════════
st.title("🧠 Simulador de Autômatos de Pilha")
st.caption("PDA (Determinístico) e NPDA (Não-Determinístico) — Exemplos canônicos (GeeksforGeeks / Sipser)")

automatas = build_automata()

# ── Seleção ──────────────────────────────────
opcao = st.selectbox("**Selecione o autômato:**", list(automatas.keys()))

automato = automatas[opcao]

# Descrição do autômato
with st.expander("📖 Sobre este autômato", expanded=True):
    st.markdown(automato.description)

# Exemplos canônicos
EXEMPLOS_ACEITOS = {
    "PDA 1 — aⁿbⁿ (n ≥ 1)":           ["ab", "aabb", "aaabbb", "aaaabbbb"],
    "PDA 2 — Parênteses balanceados":   ["()", "(())", "(()())", "((()))"],
    "NPDA 1 — Palíndromo wwᴿ":          ["aa", "abba", "ababa", "aabbaa"],
    "NPDA 2 — aⁿbⁿcᵐ ∪ aⁿbᵐcᵐ":       ["abc", "aabbc", "abcc", "aabbcc","bbbccc"],
}
EXEMPLOS_REJEITADOS = {
    "PDA 1 — aⁿbⁿ (n ≥ 1)":           ["a", "aab", "ba", "ab"],
    "PDA 2 — Parênteses balanceados":   ["(", ")(", "(()", "))("],
    "NPDA 1 — Palíndromo wwᴿ":          ["ab", "abc", "aab"],
    "NPDA 2 — aⁿbⁿcᵐ ∪ aⁿbᵐcᵐ":       ["ac", "bcc", "bcb" ,"bbbc"],
}

col_ex1, col_ex2 = st.columns(2)
with col_ex1:
    st.markdown("✅ **Exemplos aceitos:**")
    for e in EXEMPLOS_ACEITOS[opcao]:
        st.code(e, language=None)
with col_ex2:
    st.markdown("❌ **Exemplos rejeitados:**")
    for e in EXEMPLOS_REJEITADOS[opcao]:
        st.code(e, language=None)

st.divider()

# ── Entrada e controles ──────────────────────
entrada = st.text_input("**Palavra de entrada:**", EXEMPLOS_ACEITOS[opcao][1],
                         placeholder="Digite a palavra a simular...")

col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
run   = col_btn1.button("▶ Simular",  type="primary")
delay = col_btn2.slider("Velocidade (s)", 0.1, 1.5, 0.5, 0.1,
                         label_visibility="collapsed")

# ── Placeholders para atualização dinâmica ──
c_graph, c_right  = st.columns([2, 1])
graph_ph  = c_graph.empty()
stack_ph  = c_right.empty()

hist_ph   = st.empty()
result_ph = st.empty()

# ── Renderiza grafo inicial ──────────────────
graph_ph.graphviz_chart(draw_graph(automato, [automato.initial]))

import base64
def tocar_som(arquivo_audio):
    with open(arquivo_audio, "rb") as f:
        data = f.read()
        b64 = base64.b64encode(data).decode()
        # O segredo: adicionamos um timestamp no id do elemento HTML
        id_audio = f"audio_{int(time.time())}"
        md = f"""
            <audio id="{id_audio}" autoplay="true">
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
            </audio>
            """
        st.markdown(md, unsafe_allow_html=True)

# ══════════════════════════════════════════════
#  LOOP DE SIMULAÇÃO
# ══════════════════════════════════════════════
if run:
    if not entrada.strip() and opcao not in ("PDA 2 — Parênteses balanceados",):
        # Palavra vazia — ainda simula
        pass

    automato.reset()

    MAX_STEPS = 200  # Proteção contra loop infinito (ε-ciclos)
    steps = 0

    while steps < MAX_STEPS:
        steps += 1
        cont = automato.step(entrada)

        # ── Atualiza grafo ── # QUERO TODA VEZ ANTES DE MOSTRAR O ESTADO FIQUE PRETO POR 0.1 s 
        if isinstance(automato, NPDA):
            active = [c["estado"] for c in automato.configs]
        else:
            active = [automato.state]
        # piscar
        graph_ph.graphviz_chart(draw_graph(automato, active_states=[]))
        time.sleep(0.1)
        #
        graph_ph.graphviz_chart(draw_graph(automato, active))

        # ── Atualiza pilha ──
        with stack_ph.container():
            st.markdown("**🗂 Pilha(s):**")
            if isinstance(automato, NPDA):
                if not automato.configs:
                    st.code("(todos os ramos morreram)")
                else:
                    for i, c in enumerate(automato.configs[:6], 1):  # limita exibição
                        pilha_str = "".join(reversed(c["pilha"])) if c["pilha"] else "ε"
                        st.code(f"Ramo {i} [{c['estado']}]:\n{pilha_str}")
            else:
                pilha_str = "↑ Topo\n" + "\n".join(reversed(automato.stack)) if automato.stack else "(vazia)"
                st.code(pilha_str)

        # ── Histórico parcial ──
        with hist_ph.container():
            with st.expander("📋 Histórico de transições", expanded=False):
                render_history_table(automato.history)

        time.sleep(delay)

        # Para se aceitou ou não há mais movimentos
        if automato.accepted or not cont:
            break

    # ── Resultado final ──────────────────────
    with result_ph.container():
        st.divider()
        timestamp = str(time.time())

        if automato.accepted:
            st.balloons()
            st.success(f"## ✅  ACEITA   —   `{entrada}`")
            tocar_som("aeeeeee_1.mp3")
        else:
            st.error(f"## ❌  REJEITA   —   `{entrada}`")
            tocar_som("core-nao-nao-nao.mp3")
        

        st.markdown("**Tabela completa de transições executadas:**")
        render_history_table(automato.history)

