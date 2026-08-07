(function () {
  'use strict';

  var dashboardEl = document.querySelector('.dashboard-page');
  if (!dashboardEl) return;

  var sessionId = dashboardEl.dataset.sessionId;
  var POLL_INTERVAL = 2000;

  var STATE_INFO = {
    INITIALIZING:      { label: '初始化中',   icon: '◷', color: 'muted' },
    BUILDING_CONTEXT:  { label: '构建上下文', icon: '▤', color: 'muted' },
    DECIDING:          { label: '决策中',     icon: '◇', color: 'accent' },
    GOVERNING:         { label: '治理评估',   icon: '🛡', color: 'accent' },
    AWAITING_APPROVAL: { label: '等待审批',   icon: '⏸', color: 'warn' },
    EXECUTING:         { label: '执行工具',   icon: '▶', color: 'accent' },
    VALIDATING:        { label: '校验测试',   icon: '✓', color: 'accent' },
    FEEDING_BACK:      { label: '反馈回灌',   icon: '↺', color: 'warn' },
    INTERMEDIATE_VALIDATION: { label: '校验中', icon: '✓', color: 'accent' },
    FINAL_VALIDATION:  { label: '最终校验',   icon: '✓', color: 'accent' },
    COMPLETED:         { label: '已完成',     icon: '✓', color: 'success' },
    FAILED:            { label: '已失败',     icon: '✕', color: 'danger' },
    CANCELLED:         { label: '已取消',     icon: '◌', color: 'meta' },
    LIMIT_REACHED:     { label: '达到上限',   icon: '⇪', color: 'warn' }
  };

  var RUNNING_STATES = [
    'INITIALIZING', 'BUILDING_CONTEXT', 'DECIDING', 'GOVERNING',
    'AWAITING_APPROVAL', 'EXECUTING', 'VALIDATING', 'FEEDING_BACK',
    'INTERMEDIATE_VALIDATION', 'FINAL_VALIDATION'
  ];

  var TERMINAL_STATES = ['COMPLETED', 'FAILED', 'CANCELLED', 'LIMIT_REACHED'];

  var currentState = '';
  var pollTimer = null;
  var isPaused = false;

  function $(sel) { return document.querySelector(sel); }
  function $$(sel) { return document.querySelectorAll(sel); }

  // --- Backend API wrappers (sole source of truth) ---

  async function backendStep() {
    try {
      var res = await fetch('/session/' + sessionId + '/step', { method: 'POST' });
      if (!res.ok) return null;
      return await res.json();
    } catch (e) {
      console.error('Step request failed:', e);
      return null;
    }
  }

  async function backendReplay() {
    try {
      var res = await fetch('/session/' + sessionId + '/replay', { method: 'POST' });
      if (!res.ok) return null;
      return await res.json();
    } catch (e) {
      console.error('Replay request failed:', e);
      return null;
    }
  }

  // --- Polling ---

  async function pollState() {
    if (isPaused) return;
    try {
      var res = await fetch('/session/' + sessionId + '/state');
      if (!res.ok) return;
      var data = await res.json();
      if (data.error) return;
      refreshDashboard(data);
    } catch (e) {
      console.error('Poll failed:', e);
    }
  }

  function startPolling() {
    pollState();
    pollTimer = setInterval(pollState, POLL_INTERVAL);
  }

  // --- Dashboard refresh (from backend data ONLY, no local state) ---

  function refreshDashboard(data) {
    var newState = data.state || 'INITIALIZING';
    currentState = newState;
    updateCurrentStateDisplay(newState);
    updateStepper(newState);
    updateTimeline(newState);
    updateTrace(data.trace || []);
    updateGuardrail(data.guardrail_decisions || []);
    updateNavPill(newState);
  }

  function updateCurrentStateDisplay(state) {
    var info = STATE_INFO[state] || STATE_INFO.INITIALIZING;
    var monoEl = $('#current-state-mono');
    var chineseEl = $('#current-state-chinese');
    var pillEl = $('#current-state-pill');
    if (monoEl) monoEl.textContent = state;
    if (chineseEl) chineseEl.textContent = info.label;
    if (pillEl) {
      pillEl.textContent = info.icon + ' ' + info.label;
      pillEl.className = 'status-pill status-pill-' + info.color;
    }
  }

  function updateNavPill(state) {
    var info = STATE_INFO[state] || STATE_INFO.INITIALIZING;
    var pill = document.querySelector('.nav-right .state-pill');
    if (pill) {
      pill.textContent = info.icon + ' ' + info.label;
      pill.className = 'status-pill status-pill-' + info.color;
    }
  }

  function updateStepper(state) {
    var allNodes = $$('.stepper-node');
    var stateIdx = RUNNING_STATES.indexOf(state);
    var isTerminal = TERMINAL_STATES.indexOf(state) >= 0;

    allNodes.forEach(function (node) {
      var nodeState = node.dataset.state;
      node.classList.remove('current', 'completed', 'future');

      if (nodeState === state) {
        node.classList.add('current');
      } else if (isTerminal && TERMINAL_STATES.indexOf(nodeState) >= 0) {
        node.classList.add(nodeState === state ? 'current' : 'future');
      } else if (stateIdx >= 0 && RUNNING_STATES.indexOf(nodeState) >= 0 && RUNNING_STATES.indexOf(nodeState) < stateIdx) {
        node.classList.add('completed');
      } else {
        node.classList.add('future');
      }
    });
  }

  function updateTimeline(state) {
    var timelineNodes = $$('.timeline-node');
    var stateIdx = RUNNING_STATES.indexOf(state);

    timelineNodes.forEach(function (node) {
      var nodeState = node.dataset.state;
      var statusEl = node.querySelector('.timeline-status .status-pill');
      if (!statusEl) return;
      var info = STATE_INFO[nodeState] || { label: nodeState, icon: '○', color: 'idle' };

      // Always reset to idle/waiting FIRST to prevent stale markers
      statusEl.textContent = '○ 等待中';
      statusEl.className = 'status-pill status-pill-idle';

      if (nodeState === state) {
        statusEl.textContent = info.icon + ' 当前';
        statusEl.className = 'status-pill status-pill-' + (info.color || 'muted');
      } else if (stateIdx >= 0 && RUNNING_STATES.indexOf(nodeState) >= 0 && RUNNING_STATES.indexOf(nodeState) < stateIdx) {
        statusEl.textContent = '✓ 已完成';
        statusEl.className = 'status-pill status-pill-success';
      }
    });
  }

  function updateTrace(trace) {
    var placeholder = $('.trace-placeholder');
    var traceList = $('#trace-list');
    if (!trace || trace.length === 0) {
      if (placeholder) placeholder.style.display = '';
      if (traceList) { traceList.style.display = 'none'; traceList.innerHTML = ''; }
      return;
    }
    if (placeholder) placeholder.style.display = 'none';
    if (traceList) {
      traceList.style.display = '';
      traceList.innerHTML = '';
      var entries = trace.slice().reverse();
      entries.forEach(function (entry) {
        var div = document.createElement('div');
        div.className = 'trace-entry';
        if (entry.failed) {
          div.classList.add('trace-entry-failed');
        }
        var toState = entry.to || '';
        var info = STATE_INFO[toState] || STATE_INFO.INITIALIZING;
        var desc = entry.description || '';
        div.innerHTML =
          '<div class="trace-entry-header">' +
            '<span class="status-pill status-pill-' + info.color + '">' + info.icon + ' ' + info.label + '</span>' +
            '<span class="trace-entry-desc">' + desc + '</span>' +
          '</div>';
        if (entry.tool_call) {
          var tc = entry.tool_call;
          div.innerHTML +=
            '<details class="trace-tool-detail">' +
              '<summary>工具调用: ' + (tc.command || '') + '</summary>' +
              '<div class="trace-tool-body">' +
                '<code class="trace-tool-code">' + (tc.command || '') + '</code>' +
                '<span class="mono-label">MOCK 参数</span>' +
                '<code class="trace-tool-code">' + JSON.stringify(tc.args || {}) + '</code>' +
                '<span class="status-pill status-pill-' + (tc.result_ok ? 'success' : 'danger') + '">' +
                  (tc.result_ok ? '✓ 通过' : '✕ 失败') +
                '</span>' +
              '</div>' +
            '</details>';
        }
        traceList.appendChild(div);
      });
    }
  }

  function updateGuardrail(decisions) {
    var placeholder = document.querySelector('.tool-call-placeholder');
    var detail = $('#tool-call-detail');
    var guardrailDetail = $('#guardrail-detail');
    var guardrailTriple = $('#guardrail-triple');

    if (!decisions || decisions.length === 0) {
      if (placeholder) placeholder.style.display = '';
      if (detail) detail.style.display = 'none';
      if (guardrailDetail) guardrailDetail.style.display = 'none';
      if (guardrailTriple) {
        guardrailTriple.querySelectorAll('.guardrail-option').forEach(function (opt) {
          opt.classList.remove('active');
        });
      }
      return;
    }

    var lastDecision = decisions[decisions.length - 1];

    if (lastDecision.tool_call) {
      if (placeholder) placeholder.style.display = 'none';
      if (detail) detail.style.display = '';
      var codeEl = $('#tool-call-code');
      var argsEl = $('#tool-call-args');
      var resultPill = $('#tool-call-result-pill');
      if (codeEl) codeEl.textContent = lastDecision.tool_call.command || '';
      if (argsEl) argsEl.textContent = JSON.stringify(lastDecision.tool_call.args || {});
      if (resultPill) {
        resultPill.textContent = lastDecision.tool_call.result_ok ? '✓ 通过' : '✕ 失败';
        resultPill.className = 'status-pill status-pill-' + (lastDecision.tool_call.result_ok ? 'success' : 'danger');
      }
    }

    if (guardrailTriple) {
      guardrailTriple.querySelectorAll('.guardrail-option').forEach(function (opt) {
        opt.classList.remove('active');
        if (opt.dataset.decision === lastDecision.decision) {
          opt.classList.add('active');
        }
      });
    }

    if (guardrailDetail) {
      guardrailDetail.style.display = '';
      var riskList = $('#risk-list');
      var impactScope = $('#impact-scope');
      if (riskList) {
        riskList.innerHTML = '';
        (lastDecision.reasons || []).forEach(function (reason) {
          var li = document.createElement('li');
          li.textContent = reason;
          riskList.appendChild(li);
        });
      }
      if (impactScope) {
        impactScope.textContent = lastDecision.impact || 'workspace 内';
      }
    }
  }

  // --- Buttons ---

  var btnStep = $('#btn-step');
  var btnPause = $('#btn-pause');
  var btnReplay = $('#btn-replay');

  if (btnStep) {
    btnStep.addEventListener('click', function () {
      if (isPaused) return;
      backendStep().then(function (data) {
        if (data) refreshDashboard(data);
      });
    });
  }

  if (btnPause) {
    btnPause.addEventListener('click', function () {
      isPaused = !isPaused;
      btnPause.textContent = isPaused ? '▶ 继续' : '⏸ 暂停';
      if (!isPaused) pollState();
    });
  }

  if (btnReplay) {
    btnReplay.addEventListener('click', function () {
      isPaused = false;
      if (btnPause) btnPause.textContent = '⏸ 暂停';
      backendReplay().then(function (data) {
        if (data) refreshDashboard(data);
      });
    });
  }

  startPolling();
})();
