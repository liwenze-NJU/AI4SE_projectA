(function () {
  'use strict';

  var pageEl = document.querySelector('.approval-page');
  if (!pageEl) return;

  var sessionId = pageEl.dataset.sessionId;
  var TIMEOUT_SECONDS = 15;

  var btnApprove = document.getElementById('btn-approve');
  var btnReject = document.getElementById('btn-reject');
  var btnLater = document.getElementById('btn-later');
  var resultEl = document.getElementById('approval-result');
  var fillEl = document.getElementById('countdown-fill');
  var monoEl = document.getElementById('countdown-mono');

  var secondsLeft = TIMEOUT_SECONDS;
  var submitted = false;
  var timer = null;

  function disableButtons() {
    [btnApprove, btnReject, btnLater].forEach(function (btn) {
      if (btn) btn.disabled = true;
    });
  }

  function showResult(kind, text) {
    if (!resultEl) return;
    resultEl.style.display = '';
    resultEl.textContent = text;
    resultEl.className = 'approval-result approval-result-' + kind;
  }

  function renderCountdown() {
    if (!monoEl) return;
    var m = Math.floor(secondsLeft / 60);
    var s = secondsLeft % 60;
    var pad = function (n) { return (n < 10 ? '0' : '') + n; };
    monoEl.textContent = '剩余 ' + pad(m) + ':' + pad(s);
    if (fillEl) fillEl.style.width = (secondsLeft / TIMEOUT_SECONDS * 100) + '%';
    var critical = secondsLeft <= 5;
    if (critical) {
      monoEl.classList.add('countdown-critical');
      if (fillEl) fillEl.classList.add('countdown-fill-critical');
    }
  }

  function submit(decision) {
    if (submitted) return;
    submitted = true;
    disableButtons();
    fetch('/session/' + sessionId + '/approval', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision: decision, request_id: 'mock-req-1' })
    })
      .then(function (res) {
        if (!res.ok) throw new Error('approval endpoint failed');
        return res.json();
      })
      .then(function (data) {
        if (data.decision === 'approve') {
          showResult('success', '✓ ALLOW 已批准');
        } else {
          showResult('danger', '⊘ BLOCK 已拒绝');
        }
        clearInterval(timer);
        setTimeout(function () { window.location.href = '/dashboard?session=' + sessionId; }, 1500);
      })
      .catch(function (e) {
        submitted = false;
        showResult('error', '✕ 提交失败: ' + e.message);
      });
  }

  if (btnApprove) btnApprove.addEventListener('click', function () { submit('approve'); });
  if (btnReject) btnReject.addEventListener('click', function () { submit('reject'); });
  if (btnLater) btnLater.addEventListener('click', function () { window.history.back(); });

  renderCountdown();
  timer = setInterval(function () {
    secondsLeft--;
    if (secondsLeft <= 0) {
      clearInterval(timer);
      showResult('timeout', '◷ TIMEOUT 已超时');
      disableButtons();
      return;
    }
    renderCountdown();
  }, 1000);
})();
