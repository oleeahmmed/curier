module.exports = {
  apps: [{
    name: 'curier.kreatech.org',
    script: '/root/kreatech/curier/venv/bin/gunicorn',
    args: 'config.wsgi:application --bind 0.0.0.0:9825 --workers 3 --timeout 120',
    cwd: '/root/kreatech/curier/curier',
    interpreter: 'none',
    env: {
      PYTHONPATH: '/root/kreatech/curier/curier',
    },
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: '1G',
  }]
};
