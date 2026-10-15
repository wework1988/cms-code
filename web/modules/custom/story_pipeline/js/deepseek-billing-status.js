/**
 * @file
 * Schedule-based DeepSeek API peak / off-peak estimate.
 *
 * Dates are resolved in Asia/Shanghai. Weekend makeup workdays are ignored.
 * A year missing from the holiday calendar is unverified.
 */
(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports && typeof Drupal === 'undefined') {
    module.exports = api;
  }
  root.DeepSeekBillingStatus = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  var TIME_ZONE = 'Asia/Shanghai';
  var WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  var MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  var LABELS = {
    peak: 'DeepSeek: Peak',
    'off-peak': 'DeepSeek: Off-peak',
    unverified: 'Schedule unverified',
  };

  function pad(value) {
    return String(value).padStart(2, '0');
  }

  function parseClock(value) {
    if (typeof value !== 'string') {
      return null;
    }
    var match = /^([01]\d|2[0-3]):([0-5]\d)$/.exec(value);
    if (!match) {
      return null;
    }
    var hour = Number(match[1]);
    var minute = Number(match[2]);
    return {
      hour: hour,
      minute: minute,
      seconds: hour * 3600 + minute * 60,
    };
  }

  function readWindows(config) {
    if (!config || config.timeZone !== TIME_ZONE || !Array.isArray(config.peakWindows)) {
      return null;
    }
    var windows = [];
    for (var i = 0; i < config.peakWindows.length; i++) {
      var window = config.peakWindows[i];
      var start = parseClock(window && window.start);
      var end = parseClock(window && window.end);
      if (!start || !end || end.seconds <= start.seconds) {
        return null;
      }
      windows.push({ start: start.seconds, end: end.seconds, startClock: window.start, endClock: window.end });
    }
    return windows.length ? windows : null;
  }

  function holidaysForYear(config, year) {
    if (!config || !config.holidays || typeof config.holidays !== 'object') {
      return null;
    }
    var list = config.holidays[String(year)];
    if (!Array.isArray(list) || list.length === 0) {
      return null;
    }
    return new Set(list);
  }

  function wallClockParts(date) {
    var formatter = new Intl.DateTimeFormat('en-US', {
      timeZone: TIME_ZONE,
      hourCycle: 'h23',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
    var bag = {};
    formatter.formatToParts(date).forEach(function (part) {
      if (part.type !== 'literal') {
        bag[part.type] = part.value;
      }
    });
    var hour = Number(bag.hour);
    var year = Number(bag.year);
    var month = Number(bag.month);
    var day = Number(bag.day);
    if (hour === 24) {
      hour = 0;
    }
    return {
      year: year,
      month: month,
      day: day,
      hour: hour,
      minute: Number(bag.minute),
      second: Number(bag.second),
      isoDate: year + '-' + pad(month) + '-' + pad(day),
    };
  }

  function zoneOffsetMs(date) {
    var parts = wallClockParts(date);
    var asUtc = Date.UTC(parts.year, parts.month - 1, parts.day, parts.hour, parts.minute, parts.second);
    var truncated = Math.floor(date.getTime() / 1000) * 1000;
    return asUtc - truncated;
  }

  function zonedWallTimeToDate(year, month, day, hour, minute, second) {
    var utcGuess = new Date(Date.UTC(year, month - 1, day, hour, minute, second));
    var first = new Date(utcGuess.getTime() - zoneOffsetMs(utcGuess));
    return new Date(utcGuess.getTime() - zoneOffsetMs(first));
  }

  function addCivilDays(year, month, day, offset) {
    var utc = new Date(Date.UTC(year, month - 1, day + offset));
    return {
      year: utc.getUTCFullYear(),
      month: utc.getUTCMonth() + 1,
      day: utc.getUTCDate(),
    };
  }

  function civilWeekday(year, month, day) {
    return new Date(Date.UTC(year, month - 1, day)).getUTCDay();
  }

  function secondsOfDay(parts) {
    return parts.hour * 3600 + parts.minute * 60 + parts.second;
  }

  function inPeakWindow(parts, windows) {
    var seconds = secondsOfDay(parts);
    return windows.some(function (window) {
      return seconds >= window.start && seconds < window.end;
    });
  }

  function classify(parts, config, windows) {
    var holidays = holidaysForYear(config, parts.year);
    if (!windows || !holidays) {
      return { status: 'unverified', reason: windows ? 'holiday-calendar-missing' : 'schedule-invalid' };
    }
    var weekday = civilWeekday(parts.year, parts.month, parts.day);
    if (weekday === 0 || weekday === 6) {
      return { status: 'off-peak', reason: 'weekend' };
    }
    if (holidays.has(parts.isoDate)) {
      return { status: 'off-peak', reason: 'holiday' };
    }
    if (inPeakWindow(parts, windows)) {
      return { status: 'peak', reason: 'peak-window' };
    }
    return { status: 'off-peak', reason: 'off-peak-hours' };
  }

  function boundaryClocks(windows) {
    var clocks = [{ hour: 0, minute: 0, second: 0 }];
    windows.forEach(function (window) {
      clocks.push({
        hour: Math.floor(window.start / 3600),
        minute: Math.floor((window.start % 3600) / 60),
        second: 0,
      });
      clocks.push({
        hour: Math.floor(window.end / 3600),
        minute: Math.floor((window.end % 3600) / 60),
        second: 0,
      });
    });
    clocks.sort(function (a, b) {
      return (a.hour * 3600 + a.minute * 60) - (b.hour * 3600 + b.minute * 60);
    });
    return clocks;
  }

  function formatDuration(ms) {
    if (ms < 60000) {
      return Math.max(1, Math.ceil(ms / 1000)) + 's';
    }
    var totalMinutes = Math.floor(ms / 60000);
    var hours = Math.floor(totalMinutes / 60);
    var minutes = totalMinutes % 60;
    if (hours <= 0) {
      return minutes + 'm';
    }
    if (minutes === 0) {
      return hours + 'h';
    }
    return hours + 'h ' + minutes + 'm';
  }

  function emptyResult(reason) {
    return {
      status: 'unverified',
      label: LABELS.unverified,
      tone: 'unverified',
      verified: false,
      reason: reason,
      beijingTime: '',
      beijingDate: '',
      beijingDateLabel: '',
      beijingLabel: '',
      remainingMs: null,
      remainingLabel: null,
      nextStatus: null,
      nextChangeAt: null,
      countdownVerified: false,
    };
  }

  function findNextChange(now, parts, currentStatus, config, windows) {
    var clocks = boundaryClocks(windows);
    for (var dayOffset = 0; dayOffset <= 40; dayOffset++) {
      var day = addCivilDays(parts.year, parts.month, parts.day, dayOffset);
      if (!holidaysForYear(config, day.year)) {
        return null;
      }
      for (var i = 0; i < clocks.length; i++) {
        var clock = clocks[i];
        var candidate = zonedWallTimeToDate(day.year, day.month, day.day, clock.hour, clock.minute, clock.second || 0);
        if (candidate.getTime() <= now.getTime()) {
          continue;
        }
        var nextParts = wallClockParts(candidate);
        var next = classify(nextParts, config, windows);
        if (next.status !== currentStatus) {
          return { at: candidate, status: next.status };
        }
      }
    }
    return null;
  }

  function utcClock(beijingClock) {
    var parsed = parseClock(beijingClock);
    var hour = parsed.hour - 8;
    if (hour < 0) {
      hour += 24;
    }
    return pad(hour) + ':' + pad(parsed.minute);
  }

  /**
   * Explain the configured schedule in plain language.
   */
  function scheduleExplanation(config) {
    var windows = readWindows(config);
    if (!windows) {
      return 'The peak schedule could not be read, so billing status cannot be confirmed.';
    }
    var ranges = windows.map(function (window) {
      return window.startClock + '–' + window.endClock + ' Beijing (' + utcClock(window.startClock) + '–' + utcClock(window.endClock) + ' UTC)';
    }).join(' and ');
    return 'Peak hours are Monday–Friday, ' + ranges + '. Each interval includes its start and excludes its end. All other hours are off-peak. Saturdays and Sundays are off-peak all day, including weekends designated as adjusted working days. Chinese public holidays are off-peak all day.';
  }

  /**
   * Estimate DeepSeek peak billing at an absolute instant.
   *
   * @param {Date} now
   * @param {object} config
   * @return {object}
   */
  function getDeepSeekBillingStatus(now, config) {
    if (!(now instanceof Date) || Number.isNaN(now.getTime())) {
      return emptyResult('invalid-date');
    }
    var windows = readWindows(config);
    var parts = wallClockParts(now);
    var classified = classify(parts, config, windows);
    var weekday = civilWeekday(parts.year, parts.month, parts.day);
    var result = {
      status: classified.status,
      label: LABELS[classified.status],
      tone: classified.status,
      verified: classified.status !== 'unverified',
      reason: classified.reason,
      beijingTime: pad(parts.hour) + ':' + pad(parts.minute),
      beijingDate: parts.isoDate,
      beijingDateLabel: WEEKDAYS[weekday] + ' ' + parts.day + ' ' + MONTHS[parts.month - 1] + ' ' + parts.year,
      beijingLabel: pad(parts.hour) + ':' + pad(parts.minute) + ' Beijing',
      remainingMs: null,
      remainingLabel: null,
      nextStatus: null,
      nextChangeAt: null,
      countdownVerified: false,
    };
    if (!result.verified) {
      return result;
    }
    var next = findNextChange(now, parts, classified.status, config, windows);
    if (!next) {
      result.reason = classified.reason;
      result.remainingLabel = 'Next change unverified';
      return result;
    }
    result.nextStatus = next.status;
    result.nextChangeAt = next.at;
    result.remainingMs = next.at.getTime() - now.getTime();
    result.countdownVerified = true;
    result.remainingLabel = formatDuration(result.remainingMs) + ' until ' + next.status;
    return result;
  }

  return {
    getDeepSeekBillingStatus: getDeepSeekBillingStatus,
    scheduleExplanation: scheduleExplanation,
  };
});
