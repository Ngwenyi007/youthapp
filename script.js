<script>
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/static/service-worker.js')
      .then(function(reg) {
        console.log('Service worker registered ✅', reg.scope);
      })
      .catch(function(err) {
        console.error('Service worker registration failed ❌:', err);
      });
  }
</script>
