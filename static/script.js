// Role-based rank options
function updateRanks() {
    const level = document.getElementById('level-select').value;
    const rankSelect = document.getElementById('rank-select');

    let ranks = [];

    switch (level) {
        case 'member':
            ranks = ['Member'];
            break;
        case 'local':
        case 'parish':
            ranks = ['Chairman', 'Secretary', 'Treasurer', 'Matron', 'Patron', 'Organising Secretary'];
            break;
        case 'denary':
        case 'diocese':
            ranks = ['Chairman', 'Secretary', 'Treasurer', 'Matron', 'Patron', 'Chaplain', 'Organising Secretary'];
            break;
        default:
            ranks = [];
    }

    rankSelect.innerHTML = '';
    ranks.forEach(rank => {
        const option = document.createElement('option');
        option.value = rank;
        option.textContent = rank;
        rankSelect.appendChild(option);
    });
}

// Dummy post view logic (to be connected to backend later)
function showPosts(level) {
    const postArea = document.getElementById('posts');
    postArea.innerHTML = `<p>Loading ${level} level posts...</p>`;
}
function filterPosts(level) {
    const posts = document.querySelectorAll('.post');
    posts.forEach(post => {
        if (post.dataset.level === level) {
            post.style.display = 'block';
        } else {
            post.style.display = 'none';
        }
    });
}

document.addEventListener("DOMContentLoaded", () => {
  const notifyBtn = document.getElementById("notifyBtn");

  if (notifyBtn) {
    notifyBtn.addEventListener("click", async () => {
      if (!("Notification" in window)) {
        alert("This browser does not support notifications.");
        return;
      }

      if (Notification.permission === "granted") {
        showNotification();
      } else if (Notification.permission !== "denied") {
        let permission = await Notification.requestPermission();
        if (permission === "granted") {
          showNotification();
        }
      }
    });
  }

  function showNotification() {
    navigator.serviceWorker.getRegistration().then(reg => {
      if (reg) {
        reg.showNotification("Youth App Alert!", {
          body: "Thanks for enabling notifications.",
          icon: "/static/icons/icon-192.png",
          vibrate: [200, 100, 200],
          tag: "welcome",
        });
      }
    });
  }
});
// Light/Dark mode toggle
document.getElementById('toggleMode').addEventListener('click', () => {
  document.body.classList.toggle('dark-mode');
});

// Request Notifications
function requestNotificationPermission() {
  if ('Notification' in window) {
    Notification.requestPermission().then(status => {
      alert(`Notifications: ${status}`);
    });
  } else {
    alert("Notifications not supported on this browser.");
  }
}
