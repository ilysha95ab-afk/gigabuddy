import { escapeHtmlText as escapeHtml } from './utils.js';
import { apiClient } from './api_client.js';

export const GIGABUDDY_MODE = 'gigabuddy';

export const GIGABUDDY_STAGES = [
    { id: 'advisor', label: 'Советчик', helpLevel: 'подробные примеры и безопасные первые шаги' },
    { id: 'assistant', label: 'Помощник', helpLevel: 'наводящие вопросы и совместные решения' },
    { id: 'partner', label: 'Партнёр', helpLevel: 'короткий деловой challenge-mode и подсветка рисков' },
];

// Neutral fallback state (B3): NO synthetic candidate. Before a mentor's profile
// file is parsed, the panel shows a nameless, empty-track neutral state — the
// same "never fabricate" discipline the left track and persona already hold.
// The backend `build_gigabuddy_view` is the source of truth; this only fills gaps
// if the backend is momentarily unreachable, and it must stay neutral so an
// offline UI never invents an employee.
export const GIGABUDDY_DEMO_STATE = {
    productName: 'ГигаБадди',
    subtitle: 'персональный ИИ-наставник адаптации',
    activeEmployeeId: 'novice',
    employees: [],
    employee: {
        id: 'novice',
        name: '',
        role: '',
        avatar: '✨',
        theme: 'neutral',
    },
    profile: {
        name: '',
        role: '',
        department: '',
        experience: '',
        interests: [],
    },
    interface: {
        theme: 'neutral',
        accentColor: '#c93545',
        mascot: '✨',
        tone: 'friendly',
        layout: ['hero', 'stage', 'progress', 'tasks', 'next_step', 'readiness', 'questionnaire'],
    },
    track: [],
    stage: {
        id: 'advisor',
        label: 'Советчик',
        next: 'Помощник',
        helpLevel: 'Высокая опора: примеры, шаблоны, безопасные шаги',
    },
    progressPct: 0,
    nextStep: '',
    readiness: '',
    behaviorVersion: 'v1 · Советчик',
    tasks: [],
    mentorNotes: [],
    // The intake questionnaire lives in the CHAT scenario (persona-driven), not
    // as a panel block; the neutral fallback carries an empty package so no
    // synthetic questionnaire text ships in the offline UI.
    questionnairePackage: { title: '', domain: '', questions: [] },
    events: [],
};

export function isGigaBuddyMode(value) {
    return String(value || '').trim().toLowerCase() === GIGABUDDY_MODE;
}

export function applyGigaBuddyMode(settings = {}, root = document) {
    const mode = String(settings.OUROBOROS_PRODUCT_MODE || '').trim().toLowerCase();
    const enabled = isGigaBuddyMode(mode);
    document.body.dataset.productMode = enabled ? GIGABUDDY_MODE : '';
    document.body.classList.toggle('product-gigabuddy', enabled);
    if (!enabled) resetGigaBuddyInterface();
    root.querySelectorAll('[data-gigabuddy-title], #page-chat .chat-page-header .app-page-title').forEach((el) => {
        if (!el.dataset.defaultTitle) el.dataset.defaultTitle = el.textContent || 'Chat';
        el.textContent = enabled ? GIGABUDDY_DEMO_STATE.productName : (el.dataset.defaultTitle || 'Chat');
    });
    root.querySelectorAll('[data-gigabuddy-subtitle]').forEach((el) => {
        el.textContent = enabled ? GIGABUDDY_DEMO_STATE.subtitle : '';
        el.hidden = !enabled;
    });
    return enabled;
}

function normalizeView(state = {}) {
    const source = state && typeof state === 'object' ? state : {};
    return {
        ...GIGABUDDY_DEMO_STATE,
        ...source,
        employee: { ...GIGABUDDY_DEMO_STATE.employee, ...(source.employee || {}) },
        profile: { ...GIGABUDDY_DEMO_STATE.profile, ...(source.profile || {}) },
        interface: { ...GIGABUDDY_DEMO_STATE.interface, ...(source.interface || {}) },
        track: Array.isArray(source.track) ? source.track : GIGABUDDY_DEMO_STATE.track,
        stage: { ...GIGABUDDY_DEMO_STATE.stage, ...(source.stage || {}) },
        tasks: Array.isArray(source.tasks) ? source.tasks : GIGABUDDY_DEMO_STATE.tasks,
        employees: Array.isArray(source.employees) ? source.employees : GIGABUDDY_DEMO_STATE.employees,
        mentorNotes: Array.isArray(source.mentorNotes) ? source.mentorNotes : [],
        events: Array.isArray(source.events) ? source.events : [],
        questionnairePackage: { ...GIGABUDDY_DEMO_STATE.questionnairePackage, ...(source.questionnairePackage || {}) },
        knowledgeBase: normalizeKnowledgeBase(source.knowledgeBase),
    };
}

const KNOWLEDGE_STATUSES = ['empty', 'building', 'ready', 'error'];

/**
 * Normalize the knowledgeBase status descriptor from the live get_state view.
 * Shape: { status: empty|building|ready|error, docCount, chunkCount, llmBuilt }.
 * Always returns a safe object so the panel never throws on a missing/legacy view.
 */
function normalizeKnowledgeBase(kb = {}) {
    const source = kb && typeof kb === 'object' ? kb : {};
    const status = KNOWLEDGE_STATUSES.includes(source.status) ? source.status : 'empty';
    const toCount = (v) => {
        const n = Number(v);
        return Number.isFinite(n) && n >= 0 ? Math.floor(n) : 0;
    };
    return {
        status,
        docCount: toCount(source.docCount),
        chunkCount: toCount(source.chunkCount),
        llmBuilt: Boolean(source.llmBuilt),
    };
}

const HEX_ACCENT_RE = /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;
const ALLOWED_INTERFACE_THEMES = ['neutral', 'soft-cat', 'strict-terminal', 'warm-sunrise', 'ocean-calm'];
const ALLOWED_TONES = ['formal', 'friendly', 'playful'];

/**
 * Apply per-employee interface personalization (theme / accent / mascot / tone)
 * to the product shell. Uses body data attributes + a CSS custom property, so
 * no arbitrary inline styling reaches the DOM. Values are validated so a config
 * can never inject unexpected CSS.
 */
export function applyGigaBuddyInterface(iface = {}, root = document) {
    const body = document.body;
    const theme = ALLOWED_INTERFACE_THEMES.includes(iface.theme) ? iface.theme : 'neutral';
    const tone = ALLOWED_TONES.includes(iface.tone) ? iface.tone : 'friendly';
    const accent = HEX_ACCENT_RE.test(String(iface.accentColor || '')) ? iface.accentColor : '';
    body.dataset.gigabuddyTheme = theme;
    body.dataset.gigabuddyTone = tone;
    if (accent) {
        body.style.setProperty('--gigabuddy-accent', accent);
    } else {
        body.style.removeProperty('--gigabuddy-accent');
    }
    void root;
}

export function resetGigaBuddyInterface() {
    const body = document.body;
    delete body.dataset.gigabuddyTheme;
    delete body.dataset.gigabuddyTone;
    body.style.removeProperty('--gigabuddy-accent');
}

function renderEvents(state) {
    const events = state.events.length ? state.events : [
        { detail: 'Наставник видит прогресс через Telegram/admin-контур' },
        { detail: 'Если наставник меняет трек, я покажу тебе обновлённый следующий шаг мягко и без внутренних ярлыков.' },
    ];
    return events.map((event) => `<li>${escapeHtml(event.detail || event.op || '')}</li>`).join('');
}

const TRACK_STATUS_LABEL = { done: 'Пройдено', active: 'Сейчас', planned: 'Впереди' };
const TRACK_STATUS_GLYPH = { done: '✓', active: '●', planned: '○' };

/**
 * Render the LEFT adaptation-track column (B2). This shows the EMPLOYEE'S
 * onboarding stages/steps from the live `track` state — NOT the advisor→partner
 * role status (that stays in the right panel). Each stage is an expandable
 * <details> so the newcomer can "dive into" a stage and see its concrete steps.
 * When a stage has no steps yet (questionnaire is B3/C), it shows a neutral hint
 * rather than fabricating content. An empty track shows a neutral placeholder.
 */
export function renderGigaBuddyLeftTrack(view = GIGABUDDY_DEMO_STATE) {
    const state = normalizeView(view);
    const track = Array.isArray(state.track) ? state.track : [];
    const doneCount = track.filter((item) => item.status === 'done').length;
    if (!track.length) {
        return `
            <div class="gigabuddy-track-slot-head">Адаптационный трек</div>
            <div class="gigabuddy-track-empty">
                <span class="gigabuddy-track-empty-glyph" aria-hidden="true">🧭</span>
                <p>Твой персональный трек появится здесь после короткого знакомства — этапы наполнятся под твою роль.</p>
            </div>
        `;
    }
    const stages = track.map((item, index) => {
        const status = ['done', 'active', 'planned'].includes(item.status) ? item.status : 'planned';
        const steps = Array.isArray(item.steps) ? item.steps : [];
        const open = status === 'active' ? ' open' : '';
        const stepsHtml = steps.length
            ? `<ul class="gigabuddy-track-steps">${steps.map((step) => `<li>${escapeHtml(step)}</li>`).join('')}</ul>`
            : `<p class="gigabuddy-track-steps-empty">Шаги этого этапа появятся, когда мы уточним твой трек.</p>`;
        return `
            <details class="gigabuddy-track-stage" data-status="${status}"${open}>
                <summary>
                    <span class="gigabuddy-track-index" aria-hidden="true">${TRACK_STATUS_GLYPH[status]}</span>
                    <span class="gigabuddy-track-stage-main">
                        <span class="gigabuddy-track-stage-title">${escapeHtml(item.title || item.label || `Этап ${index + 1}`)}</span>
                        <span class="gigabuddy-track-stage-status">${escapeHtml(TRACK_STATUS_LABEL[status])}</span>
                    </span>
                </summary>
                <div class="gigabuddy-track-stage-body">${stepsHtml}</div>
            </details>
        `;
    }).join('');
    return `
        <div class="gigabuddy-track-slot-head">
            <span>Адаптационный трек</span>
            <span class="gigabuddy-track-progress-badge">${doneCount}/${track.length}</span>
        </div>
        <div class="gigabuddy-track-stages">${stages}</div>
    `;
}

const KNOWLEDGE_STATUS_LABEL = {
    empty: 'База знаний пуста',
    building: 'База обновляется…',
    ready: 'База обновлена',
    error: 'Не удалось построить базу',
};

/**
 * Render the knowledge-base status indicator shown next to the knowledge-folder
 * link (the mentor watches this while setting GigaBuddy up, before the newcomer
 * arrives). Status + doc/chunk counts come from the live get_state view
 * (knowledgeBase). building → pulsing "обновляется…", ready → count, empty →
 * neutral, error → honest failure (never faked ready). CSS-driven, no inline styles.
 */
function renderKnowledgeStatus(kb = {}) {
    const status = KNOWLEDGE_STATUSES.includes(kb.status) ? kb.status : 'empty';
    const docCount = Number(kb.docCount || 0);
    const chunkCount = Number(kb.chunkCount || 0);
    const label = KNOWLEDGE_STATUS_LABEL[status] || KNOWLEDGE_STATUS_LABEL.empty;
    let detail = '';
    if (status === 'ready') {
        detail = `${docCount} док. · ${chunkCount} фрагм.`;
    } else if (status === 'building') {
        detail = docCount ? `${docCount} док. в обработке` : 'извлечение и построение связей';
    } else if (status === 'error') {
        detail = 'проверьте файлы в папке знаний';
    } else {
        detail = 'наставник ещё не добавил файлы';
    }
    return `
        <div class="gigabuddy-knowledge-status" data-status="${escapeHtml(status)}" role="status" aria-live="polite">
            <span class="gigabuddy-knowledge-status-dot" aria-hidden="true"></span>
            <span class="gigabuddy-knowledge-status-label">${escapeHtml(label)}</span>
            <span class="gigabuddy-knowledge-status-detail">${escapeHtml(detail)}</span>
        </div>`;
}

export function renderGigaBuddyTrackPanel(view = GIGABUDDY_DEMO_STATE) {
    const state = normalizeView(view);
    const employee = state.employee || {};
    const stage = state.stage || {};
    const knowledgeEmployeeId = String(employee.id || state.activeEmployeeId || '').trim() || '<employee-id>';
    const knowledgePath = `~/Ouroboros/gigabuddy/employees/${knowledgeEmployeeId}/knowledge/`;
    const progress = Math.max(0, Math.min(100, Number(state.progressPct || 0)));
    const iface = state.interface || {};
    const profile = state.profile || {};
    const mascot = iface.mascot || employee.avatar || '✨';
    const interestChips = (profile.interests || []).map((interest) => `<span class="gigabuddy-chip">${escapeHtml(interest)}</span>`).join('');
    const hasName = Boolean((profile.name || employee.name || '').trim());
    const displayName = hasName ? (profile.name || employee.name) : 'Профиль ещё не загружен';
    const displayRole = hasName ? (profile.role || employee.role || 'Направление адаптации') : 'Наставник ещё не добавил профиль сотрудника';
    const trackStages = (Array.isArray(state.track) ? state.track : []).map((item) => `
        <li class="gigabuddy-adapt-stage" data-status="${escapeHtml(item.status || 'planned')}">
            <span class="gigabuddy-adapt-dot" aria-hidden="true">${item.status === 'done' ? '✓' : item.status === 'active' ? '●' : '○'}</span>
            <span class="gigabuddy-adapt-label">${escapeHtml(item.label || '')}</span>
            <span class="gigabuddy-adapt-title">${escapeHtml(item.title || '')}</span>
        </li>
    `).join('');
    return `
        <aside class="gigabuddy-track-panel" aria-label="Адаптационный трек ГигаБадди" data-gigabuddy-track-panel data-theme="${escapeHtml(iface.theme || employee.theme || 'neutral')}" data-tone="${escapeHtml(iface.tone || 'friendly')}">
            <div class="gigabuddy-track-hero" data-theme="${escapeHtml(iface.theme || employee.theme || 'default')}">
                <div class="gigabuddy-avatar" aria-hidden="true">${escapeHtml(mascot)}</div>
                <div>
                    <div class="gigabuddy-eyebrow">Адаптационный трек</div>
                    <h3>${escapeHtml(displayName)}</h3>
                    <p>${escapeHtml(displayRole)}</p>
                </div>
            </div>
            <div class="gigabuddy-demo-context">
                <span>Профиль новичка</span>
                ${hasName
                    ? `<p>${escapeHtml(`${mascot} ${displayName}${profile.department ? ' · ' + profile.department : ''}`)}</p>
                ${profile.experience ? `<p class="gigabuddy-profile-experience">${escapeHtml(profile.experience)}</p>` : ''}
                ${interestChips ? `<div class="gigabuddy-chips">${interestChips}</div>` : ''}`
                    : `<p class="gigabuddy-profile-empty">Профиль сотрудника ещё не загружен наставником. Он появится, когда наставник добавит файл профиля в папку сотрудника.</p>`}
            </div>
            <div class="gigabuddy-stage-card">
                <span class="gigabuddy-stage-label">Я сейчас: ${escapeHtml(stage.label || 'Советчик')}</span>
                <p>${escapeHtml(stage.helpLevel || '')}</p>
            </div>
            <div class="gigabuddy-progress-row">
                <span>Прогресс</span>
                <strong>${progress}%</strong>
            </div>
            <progress class="gigabuddy-progress-bar" max="100" value="${progress}" aria-label="Прогресс адаптации: ${progress}%"></progress>
            ${trackStages ? `<ul class="gigabuddy-adapt-track" aria-label="Стадии адаптационного трека">${trackStages}</ul>` : ''}
            <details class="gigabuddy-mentor-details">
                <summary>Наставнический контур</summary>
                <p>Задачи, переходы ролей и изменения трека согласуются с наставником через Telegram/admin-контур снаружи этого экрана; здесь ты видишь только текущий трек и версию поддержки.</p>
            </details>
            <div class="gigabuddy-knowledge-link">
                <span>Материалы базы знаний</span>
                <p>Первоисточники твоего отдела лежат здесь — открой при желании:</p>
                <code class="gigabuddy-knowledge-path">${escapeHtml(knowledgePath)}</code>
                ${renderKnowledgeStatus(state.knowledgeBase)}
            </div>
            <form class="gigabuddy-return-card" data-gigabuddy-return-form>
                <div>
                    <strong>Owner/admin</strong>
                    <p>Вернуться в обычный Ouroboros</p>
                </div>
                <label class="gigabuddy-return-pin">
                    <span>PIN</span>
                    <input name="pin" type="password" inputmode="numeric" autocomplete="one-time-code" maxlength="4" pattern="[0-9]{4}" placeholder="••••" aria-label="Четырёхзначный PIN возврата в Ouroboros">
                </label>
                <button type="submit" class="gigabuddy-return-button">Вернуться</button>
                <div class="gigabuddy-return-status" data-gigabuddy-return-status aria-live="polite"></div>
            </form>
            <details class="gigabuddy-mentor-events">
                <summary>События / Telegram позже</summary>
                <ul>${renderEvents(state)}</ul>
            </details>
        </aside>
    `;
}

export async function refreshGigaBuddyPanel(root = document) {
    const panel = root.querySelector('[data-gigabuddy-track-panel]');
    if (!panel || document.body.dataset.productMode !== GIGABUDDY_MODE) return null;
    const result = await apiClient.gigaBuddy('get_state');
    const view = result.view || GIGABUDDY_DEMO_STATE;
    panel.outerHTML = renderGigaBuddyTrackPanel(view);
    // B2: render the LEFT adaptation-track column from the SAME live view (single
    // get_state fetch owner). The role status stays in the right panel above.
    const trackSlot = root.querySelector('[data-gigabuddy-track-slot]');
    if (trackSlot) trackSlot.innerHTML = renderGigaBuddyLeftTrack(view);
    applyGigaBuddyInterface(normalizeView(view).interface, root);
    // This is the SINGLE get_state fetch owner: from the same view, publish the
    // novice-thread descriptor so app.js can mount the isolated center chat.
    // Always dispatch (even on a missing/zero descriptor) so the center slot can
    // deterministically fall back to the explicit unavailable placeholder.
    window.dispatchEvent(new CustomEvent('ouro:gigabuddy-novice-chat', {
        detail: (result.view && result.view.noviceChat) || {},
    }));
    return result.view || null;
}

export function bindGigaBuddyPanel(root = document) {
    // The employee-facing panel is intentionally read-mostly. Mentor/admin
    // mutations stay in the backend reducer for Telegram/admin surfaces, not in
    // the novice shell.
    void root;
}
