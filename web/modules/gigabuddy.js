import { escapeHtmlText as escapeHtml } from './utils.js';

export const GIGABUDDY_MODE = 'gigabuddy';

export const GIGABUDDY_STAGES = [
    { id: 'advisor', label: 'Советчик', helpLevel: 'подробные примеры и безопасные первые шаги' },
    { id: 'assistant', label: 'Помощник', helpLevel: 'наводящие вопросы и совместные решения' },
    { id: 'partner', label: 'Партнёр', helpLevel: 'короткий деловой challenge-mode и подсветка рисков' },
];

export const GIGABUDDY_DEMO_STATE = {
    productName: 'ГигаБадди',
    subtitle: 'персональный ИИ-наставник адаптации',
    employee: {
        id: 'demo-novice',
        name: 'Алиса',
        role: 'HR · Люди и культура',
        avatar: '🐾',
        theme: 'soft-cat',
    },
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
        { title: 'Познакомиться с процессом согласования вакансий', status: 'active' },
        { title: 'Подготовить черновик ответа заказчику', status: 'planned' },
        { title: 'Найти нужный HR-регламент в базе знаний', status: 'planned' },
    ],
    mentorEvents: [
        'Наставник видит прогресс через Telegram/admin-контур',
        'Demo accelerator: «Быстрый виток», «Откат к заботе», «Наставник вмешивается»',
    ],
};

export function isGigaBuddyMode(value) {
    return String(value || '').trim().toLowerCase() === GIGABUDDY_MODE;
}

export function applyGigaBuddyMode(settings = {}, root = document) {
    const mode = String(settings.OUROBOROS_PRODUCT_MODE || '').trim().toLowerCase();
    const enabled = isGigaBuddyMode(mode);
    document.body.dataset.productMode = enabled ? GIGABUDDY_MODE : '';
    document.body.classList.toggle('product-gigabuddy', enabled);
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

export function renderGigaBuddyTrackPanel(state = GIGABUDDY_DEMO_STATE) {
    const employee = state.employee || {};
    const stage = state.stage || {};
    const tasks = Array.isArray(state.tasks) ? state.tasks : [];
    const mentorEvents = Array.isArray(state.mentorEvents) ? state.mentorEvents : [];
    const taskItems = tasks.map((task) => `
        <li class="gigabuddy-track-task" data-status="${escapeHtml(task.status || 'planned')}">
            <span class="gigabuddy-track-check" aria-hidden="true">${task.status === 'done' ? '✓' : '□'}</span>
            <span>${escapeHtml(task.title || '')}</span>
        </li>
    `).join('');
    const eventItems = mentorEvents.map((event) => `<li>${escapeHtml(event)}</li>`).join('');
    const progress = Math.max(0, Math.min(100, Number(state.progressPct || 0)));
    return `
        <aside class="gigabuddy-track-panel" aria-label="Адаптационный трек ГигаБадди" data-gigabuddy-track-panel>
            <div class="gigabuddy-track-hero" data-theme="${escapeHtml(employee.theme || 'default')}">
                <div class="gigabuddy-avatar" aria-hidden="true">${escapeHtml(employee.avatar || '✨')}</div>
                <div>
                    <div class="gigabuddy-eyebrow">Адаптационный трек</div>
                    <h3>${escapeHtml(employee.name || 'Новичок')}</h3>
                    <p>${escapeHtml(employee.role || 'Направление адаптации')}</p>
                </div>
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
            <ul class="gigabuddy-track-list">${taskItems}</ul>
            <div class="gigabuddy-next-step">
                <span>Следующий шаг</span>
                <p>${escapeHtml(state.nextStep || '')}</p>
            </div>
            <div class="gigabuddy-readiness">
                <span>Готовность к переходу</span>
                <p>${escapeHtml(state.readiness || '')}</p>
            </div>
            <div class="gigabuddy-version-row">
                <span>${escapeHtml(state.behaviorVersion || 'v1')}</span>
                <button type="button" class="gigabuddy-rollback" disabled title="Demo surface: rollback is state/model in this increment">Откат к заботе</button>
            </div>
            <details class="gigabuddy-mentor-events">
                <summary>Telegram / наставник</summary>
                <ul>${eventItems}</ul>
            </details>
        </aside>
    `;
}
