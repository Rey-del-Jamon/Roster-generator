// Default the input to current UTC time
window.addEventListener('DOMContentLoaded', () => {
  const now = new Date();
  const isoStr = now.toISOString();
  document.getElementById('custom-date').value = isoStr.slice(0, 10);
  document.getElementById('custom-time').value = isoStr.slice(11, 16);
  
  // Check if already unlocked in this session
  if (sessionStorage.getItem('unlocked') === 'true') {
    unlockApp();
  }
});

function unlockApp() {
  document.getElementById('passcode-screen').style.display = 'none';
  document.getElementById('main-app').style.display = 'block';
}

document.getElementById('btn-submit-passcode').addEventListener('click', () => {
  const code = document.getElementById('passcode-input').value;
  if (code === '21908') {
    sessionStorage.setItem('unlocked', 'true');
    sessionStorage.setItem('passcode', code);
    unlockApp();
  } else {
    document.getElementById('passcode-error').style.display = 'block';
  }
});

document.getElementById('passcode-input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    document.getElementById('btn-submit-passcode').click();
  }
});

function generateRoster(mode) {
  const statusEl = document.getElementById('status');
  statusEl.textContent = 'Opening PDF...';
  statusEl.className = '';

  try {
    let baseUrl = '';
    if (window.location.protocol === 'file:') {
      baseUrl = 'http://localhost:8080';
    }
    
    let timeQuery = '';
    const dateVal = document.getElementById('custom-date').value;
    const timeVal = document.getElementById('custom-time').value;
    if (dateVal && timeVal) {
      // Append 'Z' to parse the user's input as UTC time
      const dateObj = new Date(`${dateVal}T${timeVal}Z`);
      const tzOffset = dateObj.getTimezoneOffset();
      timeQuery = `&time=${encodeURIComponent(dateObj.toISOString())}&tzOffset=${tzOffset}`;
    }
    
    const passcode = sessionStorage.getItem('passcode') || '21908';
    const url = `${baseUrl}/generate?mode=${mode}${timeQuery}&passcode=${passcode}`;
    window.open(url, '_blank');
    
    setTimeout(() => {
        statusEl.textContent = 'PDF opened in new tab.';
        statusEl.className = 'success';
    }, 1000);
    
  } catch (err) {
    console.error(err);
    statusEl.textContent = 'Error: ' + err.message;
    statusEl.className = 'error';
  }
}

// Redirect if opened via file://
if (window.location.protocol === 'file:') {
  document.body.innerHTML = '<h2>Redirecting to local server...</h2><p>Please wait...</p>';
  setTimeout(() => {
    window.location.href = 'http://localhost:8080';
  }, 1000);
} else {
  document.getElementById('btn-report').addEventListener('click', () => generateRoster('report'));
  document.getElementById('btn-checkout').addEventListener('click', () => generateRoster('checkout'));
}
