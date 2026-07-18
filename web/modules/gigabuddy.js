import { escapeHtmlText as escapeHtml } from './utils.js';
import { apiClient } from './api_client.js';

export const GIGABUDDY_MODE = 'gigabuddy';

export const GIGABUDDY_STAGES = [
    { id: 'advisor', label: 'Советчик', helpLevel: 'подробные примеры и безопасные первые шаги' },
    { id: 'assistant', label: 'Помощник', helpLevel: 'наводящие вопросы и совместные решения' },
    { id: 'partner', label: 'Партнёр', helpLevel: 'короткий деловой challenge-mode и подсветка рисков' },
];

export const GIGABUDDY_DEMO_STATE = {
    productName: 'ГигаБадди',
    subtitle: 'персональный ИИ-наставник адаптации',
    activeEmployeeId: 'alice-demo',
    employees: [
        { id: 'alice-demo', name: 'Алиса', role: 'HR · Люди и культура', avatar: '🐾' },
        { id: 'leonid-demo', name: 'Леонид', role: 'Разработчик · внутренний переход', avatar: '⌘' },
        { id: 'blank-demo', name: 'Новый сотрудник', role: 'Новый контекст', avatar: '✨' },
    ],
    employee: {
        id: 'alice-demo',
        name: 'Алиса',
        role: 'HR · Люди и культура',
        avatar: '🐾',
        theme: 'soft-cat',
    },
    profile: {
        name: 'Алиса',
        role: 'HR · Люди и культура',
        department: 'Люди и культура',
        experience: 'Первая роль в найме; сильна в коммуникации, осваивает внутренние регламенты.',
        interests: ['котики', 'иллюстрация', 'командные ритуалы'],
    },
    interface: {
        theme: 'soft-cat',
        accentColor: '#e8799f',
        mascot: '🐾',
        tone: 'playful',
        layout: ['hero', 'stage', 'progress', 'tasks', 'next_step', 'readiness', 'questionnaire'],
    },
    track: [
        { id: 'advisor', label: 'Советчик', title: 'Онбординг с высокой опорой', status: 'active' },
        { id: 'assistant', label: 'Помощник', title: 'Совместные задачи и разбор', status: 'planned' },
        { id: 'partner', label: 'Партнёр', title: 'Самостоятельная работа с challenge-mode', status: 'planned' },
    ],
    stage: {
        id: 'advisor',
        label: 'Советчик',
        next: 'Помощник',
        helpLevel: 'Высокая опора: примеры, шаблоны, безопасные шаги',
    },
    progressPct: 35,
    nextStep: 'Разобрать безопасный шаблон ответа внутреннему заказчику',
    readiness: 'Советчик → Помощник: требуется подтверждение наставника',
    behaviorVersion: 'v1 · мягкий Советчик',
    tasks: [
        { id: 'alice-1', title: 'Познакомиться с процессом согласования вакансий', status: 'active', source: 'demo' },
        { id: 'alice-2', title: 'Подготовить черновик ответа заказчику', status: 'planned', source: 'demo' },
        { id: 'alice-3', title: 'Найти нужный HR-регламент в базе знаний', status: 'planned', source: 'demo' },
    ],
    mentorNotes: [],
    questionnairePackage: {
        title: 'Люди и культура · базовый опросник',
        domain: 'HR / Люди и культура',
        knowledgeBaseHint: 'Подгружается вместе с доменным пакетом БЗ в следующем инкременте',
        diagnosticPolicy: 'ГигаБадди выводит уровень поддержки, автономности и стиль обучения сам; новичок не выбирает чувствительные ярлыки.',
        questions: [
            'Расскажи, какая часть новой роли сейчас кажется самой непонятной.',
            'Представь запрос от внутреннего заказчика: с чего начнёшь безопасно?',
            'Что поможет тебе быстрее войти в процесс: пример, чек-лист, схема или совместный разбор?',
        ],
    },
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
                    <h3>${escapeHtml(profile.name || employee.name || 'Новичок')}</h3>
                    <p>${escapeHtml(profile.role || employee.role || 'Направление адаптации')}</p>
                </div>
            </div>
            <div class="gigabuddy-demo-context">
                <span>Профиль новичка</span>
                <p>${escapeHtml(`${mascot} ${profile.name || employee.name || 'Новичок'}${profile.department ? ' · ' + profile.department : ''}`)}</p>
                ${profile.experience ? `<p class="gigabuddy-profile-experience">${escapeHtml(profile.experience)}</p>` : ''}
                ${interestChips ? `<div class="gigabuddy-chips">${interestChips}</div>` : ''}
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
    applyGigaBuddyInterface(normalizeView(view).interface, root);
    return result.view || null;
}

export function bindGigaBuddyPanel(root = document) {
    // The employee-facing panel is intentionally read-mostly. Mentor/admin
    // mutations stay in the backend reducer for Telegram/admin surfaces, not in
    // the novice shell.
    void root;
}
