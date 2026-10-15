const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const { getDeepSeekBillingStatus } = require('../../js/deepseek-billing-status');

const schedulePath = path.join(__dirname, '../../data/deepseek-billing-schedule.json');
const schedule = JSON.parse(fs.readFileSync(schedulePath, 'utf8'));

function at(iso) {
  return getDeepSeekBillingStatus(new Date(iso), schedule);
}

function beijing(iso) {
  return at(`${iso}+08:00`);
}

test('official calendar covers 2025 and 2026 holiday periods only', () => {
  assert.equal(schedule.holidays['2025'].length, 28);
  assert.equal(schedule.holidays['2026'].length, 33);
  assert.deepEqual(schedule.peakWindows, [
    { start: '09:00', end: '12:00' },
    { start: '14:00', end: '18:00' },
  ]);
  for (const day of schedule.ignoredAdjustedWorkingDays) {
    const year = day.slice(0, 4);
    assert.equal(schedule.holidays[year].includes(day), false, day);
  }
  assert.equal(schedule.holidays['2027'], undefined);
});

test('peak windows are inclusive at the start and exclusive at the end', () => {
  const beforeMorning = beijing('2026-10-14T08:59:59');
  const morningStart = beijing('2026-10-14T09:00:00');
  const beforeMidday = beijing('2026-10-14T11:59:59');
  const midday = beijing('2026-10-14T12:00:00');
  const beforeAfternoon = beijing('2026-10-14T13:59:59');
  const afternoonStart = beijing('2026-10-14T14:00:00');
  const beforeEvening = beijing('2026-10-14T17:59:59');
  const eveningEnd = beijing('2026-10-14T18:00:00');

  assert.equal(beforeMorning.status, 'off-peak');
  assert.equal(beforeMorning.nextChangeAt.toISOString(), '2026-10-14T01:00:00.000Z');
  assert.equal(beforeMorning.remainingMs, 1000);

  assert.equal(morningStart.status, 'peak');
  assert.equal(morningStart.reason, 'peak-window');
  assert.equal(morningStart.remainingMs, 3 * 60 * 60 * 1000);
  assert.equal(morningStart.remainingLabel, '3h until off-peak');
  assert.equal(morningStart.beijingLabel, '09:00 Beijing');

  assert.equal(beforeMidday.status, 'peak');
  assert.equal(beforeMidday.remainingMs, 1000);

  assert.equal(midday.status, 'off-peak');
  assert.equal(midday.reason, 'off-peak-hours');
  assert.equal(midday.nextChangeAt.toISOString(), '2026-10-14T06:00:00.000Z');
  assert.equal(midday.remainingLabel, '2h until peak');

  assert.equal(beforeAfternoon.status, 'off-peak');
  assert.equal(beforeAfternoon.remainingMs, 1000);
  assert.equal(afternoonStart.status, 'peak');
  assert.equal(beforeEvening.status, 'peak');
  assert.equal(beforeEvening.remainingMs, 1000);
  assert.equal(eveningEnd.status, 'off-peak');
  assert.equal(eveningEnd.nextStatus, 'peak');
});

test('Beijing midnight does not change an overnight off-peak stretch', () => {
  const before = beijing('2026-10-13T23:59:59');
  const midnight = beijing('2026-10-14T00:00:00');
  assert.equal(before.status, 'off-peak');
  assert.equal(midnight.status, 'off-peak');
  assert.equal(midnight.beijingTime, '00:00');
  assert.equal(midnight.beijingDate, '2026-10-14');
  assert.equal(midnight.nextChangeAt.toISOString(), '2026-10-14T01:00:00.000Z');
  assert.equal(midnight.remainingMs, 9 * 60 * 60 * 1000);
  assert.notEqual(before.nextChangeAt.toISOString(), '2026-10-13T16:00:00.000Z');
});

test('Friday evening skips the weekend and lands on Monday peak', () => {
  const end = beijing('2026-10-16T18:00:00');
  assert.equal(end.status, 'off-peak');
  assert.equal(end.nextChangeAt.toISOString(), new Date('2026-10-19T09:00:00+08:00').toISOString());
  assert.equal(end.remainingMs, 63 * 60 * 60 * 1000);
  assert.equal(end.remainingLabel, '63h until peak');

  const saturday = beijing('2026-10-17T10:00:00');
  assert.equal(saturday.status, 'off-peak');
  assert.equal(saturday.reason, 'weekend');
  assert.equal(saturday.nextChangeAt.toISOString(), new Date('2026-10-19T09:00:00+08:00').toISOString());
});

test('makeup weekends stay off-peak for the whole day', () => {
  for (const day of schedule.ignoredAdjustedWorkingDays) {
    const status = beijing(`${day}T10:00:00`);
    assert.equal(status.status, 'off-peak', day);
    assert.equal(status.reason, 'weekend', day);
    assert.equal(status.label, 'DeepSeek: Off-peak');
  }

  const springMakeup = beijing('2026-02-14T10:00:00');
  assert.equal(springMakeup.nextChangeAt.toISOString(), new Date('2026-02-24T09:00:00+08:00').toISOString());
  assert.equal(springMakeup.remainingLabel, '239h until peak');

  const newYearMakeup = beijing('2026-01-04T10:00:00');
  assert.equal(newYearMakeup.nextChangeAt.toISOString(), new Date('2026-01-05T09:00:00+08:00').toISOString());
});

test('Chinese public holidays are off-peak all day, including observed weekdays', () => {
  const springMonday = beijing('2026-02-16T10:00:00');
  assert.equal(springMonday.status, 'off-peak');
  assert.equal(springMonday.reason, 'holiday');
  assert.equal(springMonday.nextChangeAt.toISOString(), new Date('2026-02-24T09:00:00+08:00').toISOString());

  const springSunday = beijing('2026-02-15T10:00:00');
  assert.equal(springSunday.status, 'off-peak');
  assert.equal(springSunday.nextChangeAt.toISOString(), springMonday.nextChangeAt.toISOString());

  const nationalDay = beijing('2026-10-05T09:00:00');
  const beforePeakOnHoliday = beijing('2026-10-06T08:59:59');
  const duringPeakHourOnHoliday = beijing('2026-10-06T09:00:00');
  assert.equal(nationalDay.reason, 'holiday');
  assert.equal(beforePeakOnHoliday.status, 'off-peak');
  assert.equal(duringPeakHourOnHoliday.status, 'off-peak');
  assert.equal(duringPeakHourOnHoliday.nextChangeAt.toISOString(), new Date('2026-10-08T09:00:00+08:00').toISOString());
  assert.equal(duringPeakHourOnHoliday.remainingMs, 48 * 60 * 60 * 1000);

  const afterHoliday = beijing('2026-10-08T09:00:00');
  assert.equal(afterHoliday.status, 'peak');
});

test('missing holiday coverage does not claim a billing status', () => {
  const missing = beijing('2027-03-10T10:00:00');
  assert.equal(missing.status, 'unverified');
  assert.equal(missing.label, 'Schedule unverified');
  assert.equal(missing.tone, 'unverified');
  assert.equal(missing.verified, false);
  assert.equal(missing.remainingMs, null);
  assert.equal(missing.nextChangeAt, null);
  assert.equal(missing.beijingLabel, '10:00 Beijing');

  const emptyYear = structuredClone(schedule);
  emptyYear.holidays['2027'] = [];
  const empty = getDeepSeekBillingStatus(new Date('2027-03-10T10:00:00+08:00'), emptyYear);
  assert.equal(empty.status, 'unverified');

  assert.equal(getDeepSeekBillingStatus(new Date(), null).status, 'unverified');
  assert.equal(getDeepSeekBillingStatus(new Date('not-a-date'), schedule).status, 'unverified');
});

test('a countdown is not invented past the last verified holiday year', () => {
  const newYearsEve = beijing('2026-12-31T20:00:00');
  assert.equal(newYearsEve.status, 'off-peak');
  assert.equal(newYearsEve.verified, true);
  assert.equal(newYearsEve.countdownVerified, false);
  assert.equal(newYearsEve.remainingMs, null);
  assert.equal(newYearsEve.remainingLabel, 'Next change unverified');

  const stillCovered = beijing('2026-12-31T10:00:00');
  assert.equal(stillCovered.status, 'peak');
  assert.equal(stillCovered.nextChangeAt.toISOString(), new Date('2026-12-31T12:00:00+08:00').toISOString());
});

test('the same Beijing instant is independent of the user timezone', () => {
  const expected = {
    status: 'peak',
    beijingTime: '09:00',
    beijingDate: '2026-10-14',
  };
  const samples = [
    at('2026-10-14T01:00:00.000Z'),
    at('2026-10-13T21:00:00.000-04:00'),
    at('2026-10-14T02:00:00.000+01:00'),
  ];
  for (const sample of samples) {
    assert.equal(sample.status, expected.status);
    assert.equal(sample.beijingTime, expected.beijingTime);
    assert.equal(sample.beijingDate, expected.beijingDate);
  }

  const offPeakUtc = at('2026-10-14T10:00:00.000Z');
  assert.equal(offPeakUtc.beijingLabel, '18:00 Beijing');
  assert.equal(offPeakUtc.status, 'off-peak');

  const helperPath = path.join(__dirname, '../../js/deepseek-billing-status.js');
  const script = `
    const { getDeepSeekBillingStatus } = require(${JSON.stringify(helperPath)});
    const config = require(${JSON.stringify(schedulePath)});
    const result = getDeepSeekBillingStatus(new Date('2026-10-14T01:00:00.000Z'), config);
    process.stdout.write(JSON.stringify({ status: result.status, beijingTime: result.beijingTime }));
  `;
  for (const tz of ['UTC', 'America/New_York', 'Pacific/Auckland', 'Europe/London', 'Asia/Kolkata']) {
    const run = spawnSync(process.execPath, ['-e', script], {
      env: { ...process.env, TZ: tz },
      encoding: 'utf8',
    });
    assert.equal(run.status, 0, `${tz}\n${run.stderr}`);
    assert.deepEqual(JSON.parse(run.stdout), {
      status: 'peak',
      beijingTime: '09:00',
    });
  }
});

test('schedule and holidays stay configurable without using makeup-work flags', () => {
  const custom = structuredClone(schedule);
  custom.peakWindows = [{ start: '10:00', end: '11:00' }];
  custom.holidays['2026'] = schedule.holidays['2026'].concat(['2026-10-14']);
  const holiday = getDeepSeekBillingStatus(new Date('2026-10-14T10:30:00+08:00'), custom);
  const narrowed = getDeepSeekBillingStatus(new Date('2026-10-15T10:30:00+08:00'), custom);
  const outside = getDeepSeekBillingStatus(new Date('2026-10-15T11:00:00+08:00'), custom);
  assert.equal(holiday.status, 'off-peak');
  assert.equal(holiday.reason, 'holiday');
  assert.equal(narrowed.status, 'peak');
  assert.equal(outside.status, 'off-peak');
  assert.equal(outside.reason, 'off-peak-hours');
});
