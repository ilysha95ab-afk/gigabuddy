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
        stage: { ...GIGABUDDY_DEMO_STATE.stage, ...(source.stage || {}) },
        tasks: Array.isArray(source.tasks) ? source.tasks : GIGABUDDY_DEMO_STATE.tasks,
        employees: Array.isArray(source.employees) ? source.employees : GIGABUDDY_DEMO_STATE.employees,
        mentorNotes: Array.isArray(source.mentorNotes) ? source.mentorNotes : [],
        events: Array.isArray(source.events) ? source.events : [],
        questionnairePackage: { ...GIGABUDDY_DEMO_STATE.questionnairePackage, ...(source.questionnairePackage || {}) },
    };
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
    const taskItems = state.tasks.map((task) => `
        <li class="gigabuddy-track-task" data-status="${escapeHtml(task.status || 'planned')}">
            <span class="gigabuddy-track-check" aria-hidden="true">${task.status === 'done' ? '✓' : '□'}</span>
            <span>${escapeHtml(task.title || '')}</span>
        </li>
    `).join('');
    const questionItems = (state.questionnairePackage.questions || []).map((question) => `<li>${escapeHtml(question)}</li>`).join('');
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
            <div class="gigabuddy-demo-context">
                <span>Демо-профиль</span>
                <p>${escapeHtml(`${employee.avatar || '✨'} ${employee.name || 'Новичок'} · ${employee.role || 'Направление адаптации'}`)}</p>
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
            <div class="gigabuddy-mentor-boundary">
                <span>Наставник</span>
                <p>Задачи и переходы меняются наставником через Telegram/admin-контур; сотруднику здесь показан только текущий трек.</p>
            </div>
            <div class="gigabuddy-next-step">
                <span>Следующий шаг</span>
                <p>${escapeHtml(state.nextStep || '')}</p>
            </div>
            <div class="gigabuddy-readiness">
                <span>Готовность к переходу</span>
                <p>${escapeHtml(state.readiness || '')}</p>
            </div>
            <div class="gigabuddy-admin-surface-note">
                <span>Наставнический контур</span>
                <p>Переходы ролей и изменения трека согласуются с наставником снаружи этого экрана; здесь ты видишь текущую версию поддержки.</p>
            </div>
            <div class="gigabuddy-version-row">
                <span>${escapeHtml(state.behaviorVersion || 'v1')}</span>
                <span>Прогресс сохраняется при откате поведения</span>
            </div>
            <details class="gigabuddy-questionnaire" open>
                <summary>Базовый опросник / доменный пакет</summary>
                <p><strong>${escapeHtml(state.questionnairePackage.title || '')}</strong></p>
                <p>${escapeHtml(state.questionnairePackage.diagnosticPolicy || '')}</p>
                <ul>${questionItems}</ul>
            </details>
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
    panel.outerHTML = renderGigaBuddyTrackPanel(result.view || GIGABUDDY_DEMO_STATE);
    return result.view || null;
}

export function bindGigaBuddyPanel(root = document) {
    // The employee-facing panel is intentionally read-mostly. Mentor/admin
    // mutations stay in the backend reducer for Telegram/admin surfaces, not in
    // the novice shell.
    void root;
}
