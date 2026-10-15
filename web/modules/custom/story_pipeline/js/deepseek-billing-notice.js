/**
 * @file
 * Compact DeepSeek billing notice. Updates from the local schedule only.
 */
(function (Drupal, once, drupalSettings) {
  'use strict';

  function text(node, value) {
    if (node) {
      node.textContent = value || '';
    }
  }

  function closeNotice(root) {
    var button = root.querySelector('[data-billing-toggle]');
    root.classList.remove('is-open');
    if (button) {
      button.setAttribute('aria-expanded', 'false');
    }
  }

  function render(root, status) {
    root.dataset.tone = status.tone;
    root.setAttribute('aria-busy', 'false');
    text(root.querySelector('[data-billing-label]'), status.label);
    text(root.querySelector('[data-billing-date]'), status.beijingDateLabel);
    text(root.querySelector('[data-billing-clock]'), status.beijingLabel);
    text(root.querySelector('[data-billing-remaining]'), status.remainingLabel || '');
    var summary = root.querySelector('[data-billing-summary]');
    if (summary) {
      summary.textContent = status.verified
        ? 'Showing a schedule-based estimate for ' + status.beijingDateLabel + '.'
        : 'Holiday coverage for this Beijing year is missing, so peak or off-peak cannot be confirmed.';
    }
  }

  function delayUntilNextPaint(status) {
    var untilNextMinute = 60000 - (Date.now() % 60000) + 30;
    if (status.remainingMs == null) {
      return untilNextMinute;
    }
    return Math.min(untilNextMinute, Math.max(50, status.remainingMs + 40));
  }

  function mount(root, config) {
    var api = window.DeepSeekBillingStatus;
    var button = root.querySelector('[data-billing-toggle]');
    var tooltip = root.querySelector('[data-billing-tooltip]');
    var link = root.querySelector('[data-billing-pricing-link]');
    var timer = 0;
    var tipId = 'deepseek-billing-tip-' + Math.random().toString(36).slice(2, 8);

    if (tooltip) {
      tooltip.id = tipId;
    }
    if (button) {
      button.setAttribute('aria-controls', tipId);
    }
    if (link && config && typeof config.pricingUrl === 'string' && config.pricingUrl.indexOf('https://api-docs.deepseek.com/') === 0) {
      link.href = config.pricingUrl;
    }
    text(root.querySelector('[data-billing-schedule]'), api ? api.scheduleExplanation(config) : '');

    function refresh() {
      window.clearTimeout(timer);
      if (!api) {
        render(root, {
          tone: 'unverified',
          label: 'Schedule unverified',
          verified: false,
          beijingDateLabel: '',
          beijingLabel: '',
          remainingLabel: '',
          remainingMs: null,
        });
        return;
      }
      var status = api.getDeepSeekBillingStatus(new Date(), config || {});
      render(root, status);
      if (document.visibilityState === 'hidden') {
        if (status.remainingMs != null) {
          timer = window.setTimeout(refresh, Math.max(50, status.remainingMs + 40));
        }
        return;
      }
      timer = window.setTimeout(refresh, delayUntilNextPaint(status));
    }

    function onWake() {
      if (document.visibilityState !== 'hidden') {
        refresh();
      }
    }

    function onPointerDown(event) {
      if (!root.contains(event.target)) {
        closeNotice(root);
      }
    }

    function onKeyDown(event) {
      if (event.key === 'Escape' && root.classList.contains('is-open')) {
        closeNotice(root);
        if (button) {
          button.focus();
        }
      }
    }

    function onToggle() {
      var open = root.classList.toggle('is-open');
      if (button) {
        button.setAttribute('aria-expanded', open ? 'true' : 'false');
      }
    }

    if (button) {
      button.addEventListener('click', onToggle);
    }
    document.addEventListener('visibilitychange', onWake);
    window.addEventListener('focus', onWake);
    window.addEventListener('pageshow', onWake);
    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    refresh();

    root.deepseekBillingCleanup = function () {
      window.clearTimeout(timer);
      if (button) {
        button.removeEventListener('click', onToggle);
      }
      document.removeEventListener('visibilitychange', onWake);
      window.removeEventListener('focus', onWake);
      window.removeEventListener('pageshow', onWake);
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }

  Drupal.behaviors.deepseekBillingNotice = {
    attach: function (context) {
      once('deepseek-billing-notice', '[data-deepseek-billing-notice]', context).forEach(function (root) {
        mount(root, drupalSettings.deepseekBilling || {});
      });
    },
    detach: function (context) {
      once.remove('deepseek-billing-notice', '[data-deepseek-billing-notice]', context).forEach(function (root) {
        if (root.deepseekBillingCleanup) {
          root.deepseekBillingCleanup();
          delete root.deepseekBillingCleanup;
        }
      });
    },
  };
})(Drupal, once, drupalSettings);
