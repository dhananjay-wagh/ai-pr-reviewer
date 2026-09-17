'use strict';
const byId = id => document.getElementById(id);
let token = '';
let jobs = [];
let selectedJob = null;
async function api(path, method = 'GET') {
  const response = await fetch(path, {method, headers: {Authorization: `Bearer ${token}`}, cache: 'no-store'});
  if (response.status === 401) { disconnect(); throw new Error('Access token was not accepted.'); }
  if (!response.ok) throw new Error('Could not load review data. Try refreshing.');
  return response.json();
}
function disconnect() {
  token = ''; jobs = []; selectedJob = null;
  byId('workspace').hidden = true; byId('login').hidden = false;
  byId('token').value = ''; byId('jobs').replaceChildren(); byId('findings').replaceChildren();
  for (const id of ['detail-title', 'detail-scope', 'detail-meta', 'completed', 'active', 'latency', 'tokens', 'count'])
    byId(id).textContent = '';
  byId('detail').hidden = true;
}
function text(tag, value, className) {
  const element = document.createElement(tag); element.textContent = value;
  if (className) element.className = className;
  return element;
}
function showDetail(job) {
  selectedJob = job;
  byId('retry-job').hidden = job.status !== 'failed';
  const result = job.result || {};
  byId('detail').hidden = false;
  byId('detail-title').textContent = `${job.repo} #${job.number}${result.demo ? ' · DEMO DATA' : ''}`;
  byId('detail-scope').textContent = job.error ? `Review failed: ${job.error}` :
    result.complete === false ? 'Partial coverage. Some changes were not reviewed.' :
    job.status === 'completed' ? 'Completed within the configured review scope.' : `Job is ${job.status}.`;
  byId('detail-meta').textContent = JSON.stringify({commit: job.sha, attempts: job.attempts,
    model: result.model, duration_seconds: result.duration_seconds,
    prompt_tokens: result.prompt_tokens, completion_tokens: result.completion_tokens,
    reviewed_files: result.reviewed_files, ignored_files: result.ignored_files,
    skipped_files: result.skipped_files}, null, 2);
  byId('findings').replaceChildren();
  for (const finding of result.findings || []) {
    const article = text('article', '', 'finding');
    article.append(text('h3', `${finding.severity} · ${finding.category}`),
      text('small', `${finding.file}:${finding.line} · ${finding.side}`), text('p', finding.comment));
    byId('findings').append(article);
  }
  if (job.status === 'completed' && !(result.findings || []).length)
    byId('findings').append(text('p', 'No qualifying findings. This is not approval.'));
  byId('detail').scrollIntoView({behavior: 'smooth', block: 'nearest'});
}
async function refresh() {
  byId('refresh').disabled = true; byId('message').textContent = 'Loading review activity…';
  try {
    const [history, metrics] = await Promise.all([api('/api/jobs'), api('/api/metrics')]);
    if (!token) return;
    jobs = history.jobs; const counts = metrics.jobs_by_status;
    byId('completed').textContent = counts.completed || 0;
    byId('active').textContent = (counts.running || 0) + (counts.queued || 0);
    byId('latency').textContent = metrics.median_review_seconds == null ? '—' : `${metrics.median_review_seconds.toFixed(1)}s`;
    byId('tokens').textContent = (metrics.prompt_tokens + metrics.completion_tokens).toLocaleString();
    byId('count').textContent = jobs.length; byId('jobs').replaceChildren();
    byId('empty').hidden = jobs.length > 0;
    for (const job of jobs) {
      const row = document.createElement('tr'); const cell = document.createElement('td');
      const button = text('button', `${job.repo} #${job.number}${job.result?.demo ? ' · DEMO' : ''}`, 'job-link');
      button.addEventListener('click', () => showDetail(job)); cell.append(button);
      const status = document.createElement('td'); status.append(text('span', job.status, `badge ${job.status}`));
      row.append(cell, text('td', job.sha.slice(0, 7), 'commit'), status,
        text('td', job.result?.findings?.length ?? '—'), text('td', new Date(job.created * 1000).toLocaleString()));
      byId('jobs').append(row);
    }
    byId('login').hidden = true; byId('workspace').hidden = false;
    byId('message').textContent = 'Connected · Refresh to load the latest activity.';
  } catch (error) { byId('message').textContent = error.message; }
  finally { byId('refresh').disabled = false; }
}
byId('login-form').addEventListener('submit', event => {event.preventDefault(); token = byId('token').value; byId('token').value = ''; refresh();});
byId('refresh').addEventListener('click', refresh);
byId('logout').addEventListener('click', () => {disconnect(); byId('message').textContent = 'Disconnected.';});
byId('close-detail').addEventListener('click', () => {byId('detail').hidden = true;});
byId('retry-job').addEventListener('click', async () => {
  if (!selectedJob || selectedJob.status !== 'failed') return;
  byId('retry-job').disabled = true;
  try {
    await api(`/api/jobs/${encodeURIComponent(selectedJob.id)}/retry`, 'POST');
    byId('detail').hidden = true;
    await refresh();
  } catch (error) { byId('message').textContent = error.message; }
  finally { byId('retry-job').disabled = false; }
});
