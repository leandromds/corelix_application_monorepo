# DESIGN_SYSTEM.md
> Referência de design para a IA implementar componentes da Secretária Digital.
> **Baseado exatamente no wireframe `wireframe-corelix-dark.html`.**
> Não invente estilos. Use as classes e tokens definidos aqui.

---

## Setup obrigatório

O arquivo `src/globals.css` contém **todos** os tokens de design e classes utilitárias.
Ele deve ser importado uma única vez em `src/main.tsx`:

```tsx
import './globals.css'
```

O Tailwind ainda é usado para **layout e espaçamentos pontuais** (grid, flex, gap, w-, h-).
Para **aparência visual** (cores, bordas, sombras, backgrounds), use **as classes CSS do globals.css** — nunca invente valores com Tailwind.

---

## Design Tokens

Todos os tokens estão disponíveis como CSS custom properties. Use via `style={{ color: 'var(--text-muted)' }}` ou via classe CSS.

| Token | Valor | Uso |
|---|---|---|
| `--bg-page` | `hsl(225,20%,9%)` | background do body |
| `--bg-surface` | `rgba(255,255,255,0.05)` | cards, inputs |
| `--bg-elevated` | `rgba(255,255,255,0.08)` | hover states, cards elevados |
| `--bg-selected` | `rgba(139,92,246,0.15)` | nav ativo, config tab ativo |
| `--border-default` | `rgba(255,255,255,0.10)` | bordas padrão |
| `--border-strong` | `rgba(255,255,255,0.18)` | bordas com mais destaque |
| `--border-purple` | `rgba(139,92,246,0.45)` | bordas de estado ativo |
| `--text-primary` | `rgba(255,255,255,0.95)` | texto principal |
| `--text-muted` | `rgba(255,255,255,0.50)` | texto secundário |
| `--text-subtle` | `rgba(255,255,255,0.30)` | texto de baixo contraste |
| `--purple-500` | `hsl(260,95%,63%)` | cor primária |
| `--purple-glow` | `rgba(139,92,246,0.35)` | box-shadow glow |
| `--success` / `--success-bg` / `--success-border` | verde | estados de sucesso |
| `--warning` / `--warning-bg` / `--warning-border` | amarelo | estados de aviso |
| `--danger` / `--danger-bg` / `--danger-border` | vermelho | estados de erro |
| `--info` / `--info-bg` / `--info-border` | azul | estados informativos |
| `--sidebar-width` | `256px` | largura do sidebar |
| `--topbar-height` | `52px` | altura do topbar |
| `--radius-sm` | `0.5rem` | border-radius pequeno |
| `--radius-md` | `0.75rem` | border-radius médio |
| `--radius-lg` | `1rem` | border-radius grande |
| `--radius-xl` | `1.5rem` | border-radius extra-large |
| `--radius-full` | `9999px` | border-radius pill |

---

## Estrutura de Layout

```tsx
// Sempre envolva com bg-blobs para os blobs de fundo
<div>
  <div className="bg-blobs">
    <div className="blob blob-1" />
    <div className="blob blob-2" />
  </div>

  <div className="app-shell">
    <aside className="sidebar">…</aside>
    <div className="main-content">
      <header className="topbar">…</header>
      <div className="screen-area">
        {/* conteúdo da tela */}
      </div>
    </div>
  </div>

  <nav className="mobile-nav">…</nav>
</div>
```

---

## Componentes

### Sidebar

```tsx
<aside className="sidebar"> {/* adicione "collapsed" para recolher */}
  <div className="sidebar-logo">
    <div className="logo-icon">
      <i className="fas fa-stethoscope" style={{ fontSize: 13, color: 'hsl(270,95%,75%)' }} />
    </div>
    <span className="logo-text">Secretária Digital</span>
  </div>

  <div style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden' }}>
    <div className="sidebar-section-label">Menu</div>
    <nav>
      <a className={`nav-item ${isActive ? 'active' : ''}`} onClick={…}>
        <i className="nav-icon fas fa-home" />
        <span className="nav-item-label">Início</span>
      </a>
      {/* badge de notificação */}
      <a className="nav-item" onClick={…}>
        <i className="nav-icon fab fa-whatsapp" />
        <span className="nav-item-label">WhatsApp</span>
        <span className="sidebar-badge">3</span>
      </a>
    </nav>
  </div>

  <div className="sidebar-footer">
    <div className="sidebar-user">
      <div className="avatar avatar-md">AB</div>
      <div className="sidebar-user-info">
        <div style={{ fontSize: 12, fontWeight: 600 }}>Ana Beatriz</div>
        <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Psicóloga</div>
      </div>
    </div>
  </div>
</aside>
```

---

### Topbar

```tsx
<header className="topbar">
  <button className="icon-btn" onClick={toggleSidebar}>
    <i className="fas fa-bars" />
  </button>
  <span className="topbar-breadcrumb">Início</span>
  <span className="topbar-date">Quarta, 7 mai 2025</span>
  <div style={{ position: 'relative' }}>
    <button className="icon-btn">
      <i className="fas fa-bell" />
      <span className="notif-badge" />
    </button>
  </div>
  <div className="avatar avatar-sm">AB</div>
</header>
```

---

### Glass Card

```tsx
{/* Card padrão */}
<div className="glass-card">…</div>

{/* Com glow roxo */}
<div className="glass-card glow">…</div>

{/* Fundo levemente mais claro */}
<div className="glass-card elevated">…</div>

{/* Com gradient border (efeito premium) */}
<div className="glass-card bordered">…</div>

{/* Título do card */}
<div className="card-title">
  Sessões de hoje
  <button className="btn-link">Ver todas</button>
</div>

{/* Divisor dentro do card */}
<div className="card-divider" />
```

---

### KPI Card

```tsx
<div className="glass-card glow bordered">
  <div className="kpi-label">Sessões este mês</div>
  <div className="kpi-value" style={{ color: 'hsl(270,95%,75%)' }}>24</div>
  <div className="kpi-sub">↑ 4 vs mês anterior</div>
</div>
```

---

### Badges

```tsx
<span className="badge badge-confirmed">Confirmado</span>
<span className="badge badge-pending">Pendente</span>
<span className="badge badge-cancelled">Cancelado</span>
<span className="badge badge-noshow">Faltou</span>
<span className="badge badge-ai"><i className="fas fa-robot" /> IA</span>
<span className="badge badge-purple">Novo</span>
```

---

### Botões

```tsx
{/* Primário — ação principal */}
<button className="btn-primary">
  <i className="fas fa-plus" /> Nova sessão
</button>

{/* Secundário — ação auxiliar */}
<button className="btn-secondary">Cancelar</button>

{/* Link roxo */}
<button className="btn-link">Ver todas →</button>
```

---

### Formulário

```tsx
<div>
  <label className="label">Nome do paciente</label>
  <input className="input" type="text" placeholder="Ex: Maria Silva" />
</div>

<div>
  <label className="label">Duração</label>
  <select className="input" style={{ background: 'var(--bg-surface)', color: 'var(--text-primary)' }}>
    <option>50 min</option>
    <option>60 min</option>
  </select>
</div>

<div>
  <label className="label">Observações</label>
  <textarea className="input" rows={4} style={{ resize: 'vertical' }} />
</div>
```

---

### Toggle (switch)

```tsx
<label className="toggle">
  <input type="checkbox" checked={value} onChange={onChange} />
  <span className="toggle-slider" />
</label>
```

---

### Modal

```tsx
{isOpen && (
  <div className="modal-overlay" onClick={onClose}>
    <div className="modal" onClick={e => e.stopPropagation()}>
      <div className="modal-header">
        <span className="modal-title">Nova sessão</span>
        <button className="modal-close" onClick={onClose}>
          <i className="fas fa-xmark" />
        </button>
      </div>

      {/* conteúdo */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        …
      </div>

      <div className="modal-footer">
        <button className="btn-secondary" onClick={onClose}>Cancelar</button>
        <button className="btn-primary" onClick={onSave}>
          <i className="fas fa-floppy-disk" /> Salvar
        </button>
      </div>
    </div>
  </div>
)}
```

---

### Session Row (lista de sessões)

```tsx
<div className="session-row">
  <span className="session-time">09:00</span>
  <div className="avatar avatar-sm">MS</div>
  <div style={{ flex: 1, minWidth: 0 }}>
    <div className="session-name">Maria Silva</div>
    <div className="session-desc">Psicoterapia · 50 min</div>
  </div>
  <span className="badge badge-confirmed">Confirmado</span>
  <button className="icon-btn"><i className="fas fa-ellipsis" /></button>
</div>
```

---

### WhatsApp item

```tsx
<div className="wa-item">
  <div className="avatar avatar-md">MS</div>
  <div style={{ flex: 1, minWidth: 0 }}>
    <div className="wa-name">
      Maria Silva
      <span className="wa-time">14:32</span>
    </div>
    <div className="wa-preview">Oi, posso remarcar para…</div>
  </div>
  {/* badge de não lido */}
  <span style={{
    background: 'var(--danger)', color: 'white',
    fontSize: 9, fontWeight: 700,
    borderRadius: 'var(--radius-full)',
    padding: '1px 6px'
  }}>2</span>
</div>
```

---

### Data Table

```tsx
<table className="data-table">
  <thead>
    <tr>
      <th>Paciente</th>
      <th>Data</th>
      <th>Status</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Maria Silva</td>
      <td>07/05/2025</td>
      <td><span className="badge badge-confirmed">Confirmado</span></td>
    </tr>
  </tbody>
</table>
```

---

### Alert / Banner

```tsx
{/* Sucesso */}
<div className="alert alert-success">
  <i className="fas fa-circle-check" style={{ color: 'var(--success)', fontSize: 16 }} />
  <div>
    <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--success)' }}>WhatsApp Conectado</div>
    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>+55 11 99999-8888</div>
  </div>
</div>

{/* Roxo informativo */}
<div className="alert alert-purple">…</div>

{/* Azul informativo */}
<div className="alert alert-info">…</div>
```

---

### Empty State

```tsx
<div className="empty-state">
  <div className="empty-icon">
    <i className="fas fa-calendar-xmark" />
  </div>
  <div className="empty-title">Nenhuma sessão hoje</div>
  <p className="empty-desc">Quando você agendar sessões elas aparecerão aqui.</p>
  <button className="btn-primary"><i className="fas fa-plus" /> Agendar sessão</button>
</div>
```

---

### Progress Bar

```tsx
<div className="progress-track">
  <div className="progress-fill" style={{ width: '72%' }} />
</div>
```

---

### Skeleton (loading)

```tsx
{/* Simule qualquer elemento em carregamento */}
<div className="skeleton" style={{ height: 14, width: '60%', marginBottom: 8 }} />
<div className="skeleton" style={{ height: 14, width: '40%' }} />
```

---

### Config Tab (sidebar de configurações)

```tsx
<button
  className={`config-tab ${active === 'perfil' ? 'active' : ''}`}
  onClick={() => setActive('perfil')}
>
  <i className="fas fa-user" />
  Perfil
</button>
```

---

### Avatar

```tsx
{/* Iniciais */}
<div className="avatar avatar-sm">AB</div>  {/* 28px */}
<div className="avatar avatar-md">AB</div>  {/* 34px */}
<div className="avatar avatar-lg">AB</div>  {/* 40px */}
```

---

## Tipografia

| Uso | Fonte | Tamanho | Peso |
|---|---|---|---|
| Títulos, KPI, logo | `Plus Jakarta Sans` | 15–30px | 700–800 |
| Card titles | `Plus Jakarta Sans` | 13px | 700 |
| Corpo, inputs | `Inter` | 12–13px | 400–600 |
| Labels de campos | `Inter` | 11px | 600 uppercase |
| Badges, tags | `Inter` | 10px | 700 |
| Timestamps | `Inter` | 10–11px | 400–500 |

```tsx
{/* Título de seção */}
<h3 style={{ fontFamily: "'Plus Jakarta Sans', sans-serif", fontSize: 15, fontWeight: 700 }}>
  Título
</h3>

{/* Texto muted */}
<p style={{ fontSize: 12, color: 'var(--text-muted)' }}>Texto secundário</p>
```

---

## Ícones

Use **Font Awesome 6** (já carregado via CDN no index.html):

```tsx
<i className="fas fa-home" />          {/* sólido */}
<i className="far fa-calendar" />     {/* outline */}
<i className="fab fa-whatsapp" />     {/* brand */}
```

Ícones comuns no projeto:
- `fas fa-home` — Início
- `fas fa-calendar-alt` — Agenda
- `fas fa-users` — Clientes
- `fab fa-whatsapp` — WhatsApp
- `fas fa-chart-line` — Relatórios
- `fas fa-cog` — Configurações
- `fas fa-plus` — Adicionar
- `fas fa-floppy-disk` — Salvar
- `fas fa-xmark` — Fechar
- `fas fa-ellipsis` — Mais opções
- `fas fa-robot` — IA

---

## Regras para a IA

1. **Nunca use classes Tailwind de cor** (`bg-purple-500`, `text-white`, `border-gray-700`). Use os tokens CSS (`var(--bg-surface)`, `var(--text-muted)`, etc.).
2. **Nunca recrie os estilos de `.glass-card`, `.btn-primary`, `.badge`, `.input`, `.modal` etc.** — essas classes já existem no `globals.css`. Apenas aplique-as.
3. **Use Tailwind apenas para layout**: `flex`, `grid`, `gap-4`, `w-full`, `col-span-2`, `mt-4`, `min-w-0`, etc.
4. **Espaçamentos internos de componentes** devem respeitar os valores do wireframe: padding dos cards é `20px`, session-row é `11px 0`, inputs são `8px 12px`.
5. **Ao criar modais**, sempre use `.modal-overlay` + `.modal` + `.modal-header` + `.modal-footer` como estrutura.
6. **Fontes**: aplique `fontFamily: "'Plus Jakarta Sans', sans-serif"` em títulos e valores KPI. Corpo usa Inter por padrão via CSS.
7. **Nunca use `background: white` ou `color: black`** — este é um design dark glass, sem superfícies brancas.
