(function (Drupal, drupalSettings, once) {
  'use strict';

  const MAX_CONSOLE_LINES = 500;
  const consoleOffsets = {};
  let consolePaused = false;
  let userScrolledUp = false;

  function applyProgress(nid, data) {
    const wrap = document.querySelector('[data-story-progress="' + nid + '"]');
    if (!wrap || !data) {
      return;
    }
    const bar = wrap.querySelector('.story-pipeline-progress__bar');
    const pct = wrap.querySelector('.story-pipeline-progress__pct');
    const label = wrap.querySelector('.story-pipeline-progress__label');
    const detail = wrap.querySelector('.story-pipeline-progress__detail');
    const track = wrap.querySelector('.story-pipeline-progress');

    const state = data.state || 'idle';
    const percent = Math.max(0, Math.min(100, parseInt(data.percent, 10) || 0));

    track.className = 'story-pipeline-progress story-pipeline-progress--' + state;
    if (bar) {
      bar.style.width = state === 'idle' ? '0%' : percent + '%';
    }
    if (pct) {
      pct.textContent = state === 'idle' ? '—' : percent + '%';
    }
    if (label) {
      label.textContent = data.label || '';
    }
    if (detail) {
      detail.textContent = data.detail || '';
      detail.style.display = data.detail ? 'block' : 'none';
    }
  }

  function pollProgress(settings) {
    const url = settings.progressUrl;
    if (!url) {
      return;
    }
    fetch(url, {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    })
      .then(function (response) {
        return response.json();
      })
      .then(function (json) {
        Object.keys(json).forEach(function (nid) {
          applyProgress(nid, json[nid]);
        });
      })
      .catch(function () {
        // Ignore transient network errors.
      });
  }

  function lineClass(text) {
    if (/error|exception|traceback|failed|fatal/i.test(text)) {
      return 'story-pipeline-console__line--error';
    }
    if (/PROGRESS|done\./i.test(text)) {
      return 'story-pipeline-console__line--progress';
    }
    if (/Stage [ABC]|step \d/i.test(text)) {
      return 'story-pipeline-console__line--stage';
    }
    return '';
  }

  function appendConsoleLines(lines) {
    const body = document.getElementById('story-pipeline-console-body');
    if (!body || !lines || lines.length === 0) {
      return;
    }

    const placeholder = body.querySelector('.story-pipeline-console__placeholder');
    if (placeholder) {
      placeholder.remove();
    }

    lines.forEach(function (entry) {
      const div = document.createElement('div');
      div.className = 'story-pipeline-console__line ' + lineClass(entry.text || '');
      div.textContent = entry.text || '';
      body.appendChild(div);
    });

    while (body.childElementCount > MAX_CONSOLE_LINES) {
      body.removeChild(body.firstElementChild);
    }

    if (!userScrolledUp) {
      body.scrollTop = body.scrollHeight;
    }
  }

  function updateConsoleStatus(data) {
    const status = document.getElementById('story-pipeline-console-status');
    const jobsEl = document.getElementById('story-pipeline-console-jobs');
    if (!status) {
      return;
    }

    const running = data.running_count || 0;
    if (running > 0) {
      status.textContent = Drupal.t('@count job(s) running', { '@count': running });
      status.className = 'story-pipeline-console__status story-pipeline-console__status--active';
    }
    else {
      status.textContent = Drupal.t('No jobs running');
      status.className = 'story-pipeline-console__status';
    }

    if (jobsEl && data.jobs) {
      jobsEl.innerHTML = '';
      data.jobs.forEach(function (job) {
        const chip = document.createElement('span');
        chip.className = 'story-pipeline-console__job-chip story-pipeline-console__job-chip--' + (job.state || 'idle');
        chip.textContent = '#' + job.id + ' ' + job.title + ' — ' + (job.percent || 0) + '% ' + (job.label || '');
        jobsEl.appendChild(chip);
      });
    }
  }

  function pollConsole(settings) {
    if (consolePaused || !settings.consoleUrl) {
      return;
    }

    const params = new URLSearchParams();
    Object.keys(consoleOffsets).forEach(function (nid) {
      params.append('offsets[' + nid + ']', consoleOffsets[nid]);
    });

    const url = settings.consoleUrl + (params.toString() ? '?' + params.toString() : '');

    fetch(url, {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    })
      .then(function (response) {
        return response.json();
      })
      .then(function (data) {
        updateConsoleStatus(data);

        if (data.streams) {
          const allLines = [];
          Object.keys(data.streams).forEach(function (nid) {
            const stream = data.streams[nid];
            if (stream.offset !== undefined) {
              consoleOffsets[nid] = stream.offset;
            }
            if (stream.lines && stream.lines.length) {
              stream.lines.forEach(function (line) {
                allLines.push({ ts: line.ts || 0, text: line.text });
              });
            }
          });
          allLines.sort(function (a, b) {
            return (a.ts || 0) - (b.ts || 0);
          });
          appendConsoleLines(allLines);
        }
      })
      .catch(function () {
        // Ignore transient network errors.
      });
  }

  Drupal.behaviors.storyPipelineRunProgress = {
    attach: function (context) {
      const settings = drupalSettings.storyPipelineRun || {};

      once('story-pipeline-run-progress', 'body', context).forEach(function () {
        if (settings.progressUrl) {
          const progressInterval = settings.pollIntervalMs || 8000;
          pollProgress(settings);
          setInterval(function () {
            pollProgress(settings);
          }, progressInterval);
        }

        if (settings.consoleUrl) {
          const consoleInterval = settings.consolePollIntervalMs || 4000;
          pollConsole(settings);
          setInterval(function () {
            pollConsole(settings);
          }, consoleInterval);
        }
      });

      once('story-pipeline-console-clear', '#story-pipeline-console-clear', context).forEach(function (btn) {
        btn.addEventListener('click', function () {
          const body = document.getElementById('story-pipeline-console-body');
          if (body) {
            body.innerHTML = '<div class="story-pipeline-console__placeholder">' +
              Drupal.t('Console cleared. New log lines will appear when jobs run.') + '</div>';
          }
          Object.keys(consoleOffsets).forEach(function (key) {
            delete consoleOffsets[key];
          });
        });
      });

      once('story-pipeline-console-pause', '#story-pipeline-console-pause', context).forEach(function (btn) {
        btn.addEventListener('click', function () {
          consolePaused = !consolePaused;
          btn.textContent = consolePaused ? Drupal.t('Resume') : Drupal.t('Pause');
          btn.setAttribute('aria-pressed', consolePaused ? 'true' : 'false');
        });
      });

      once('story-pipeline-console-scroll', '#story-pipeline-console-body', context).forEach(function (body) {
        body.addEventListener('scroll', function () {
          const atBottom = body.scrollHeight - body.scrollTop - body.clientHeight < 40;
          userScrolledUp = !atBottom;
        });
      });
    },
  };
})(Drupal, drupalSettings, once);
