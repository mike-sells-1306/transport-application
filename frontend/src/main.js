async function checkHealth() {
  try {
    const res = await fetch('/api/health', { method: 'GET' });
    const data = await res.json();
    document.getElementById('status').innerText = 'Backend: ' + (data.status || JSON.stringify(data));
  } catch (e) {
    document.getElementById('status').innerText = 'Backend not reachable';
  }
}

checkHealth();
