(function () {
  if (typeof Chart === 'undefined') return;

  // Per-team points-per-game bar chart. Each canvas carries a sibling
  // <script type="application/json" id="{canvas-id}-data"> with the
  // form_rows payload from the API.
  document.querySelectorAll('canvas.form-points-chart').forEach(function (canvas) {
    var node = document.getElementById(canvas.id + '-data');
    if (!node) return;
    var rows;
    try { rows = JSON.parse(node.textContent); } catch (_) { return; }
    if (!rows || !rows.length) return;
    // Oldest → most-recent on the x-axis (API returns most-recent-first).
    rows = rows.slice().reverse();
    var labels = rows.map(function (r) {
      var d = new Date(r.start_time);
      return isNaN(d) ? '?' : (d.toLocaleString('en-GB', {day:'numeric', month:'short'}));
    });
    var data = rows.map(function (r) { return r.points; });
    var colors = rows.map(function (r) {
      if (r.result === 'W') return 'rgba(25, 135, 84, 0.85)';
      if (r.result === 'D') return 'rgba(108, 117, 125, 0.85)';
      if (r.result === 'L') return 'rgba(220, 53, 69, 0.85)';
      return 'rgba(173, 181, 189, 0.6)';
    });
    new Chart(canvas, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          data: data,
          backgroundColor: colors,
          borderWidth: 0,
        }],
      },
      options: {
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                var r = rows[ctx.dataIndex];
                return (r.result || '?') + ' ' + r.team_score + '-' + r.opponent_score +
                  ' (' + r.venue + ' vs ' + (r.opponent_name || '?') + ')';
              },
            },
          },
        },
        scales: {
          y: { beginAtZero: true, max: 3, ticks: { stepSize: 1 } },
          x: { ticks: { autoSkip: true, maxRotation: 0 } },
        },
      },
    });
  });

  // Combined-goals chart over H2H meetings.
  var h2hCanvas = document.getElementById('h2h-combined-chart');
  var h2hData = document.getElementById('h2h-combined-chart-data');
  if (h2hCanvas && h2hData && typeof Chart !== 'undefined') {
    var meetings;
    try { meetings = JSON.parse(h2hData.textContent); } catch (_) { meetings = []; }
    if (meetings.length) {
      // API returns most-recent-first; oldest → newest reads more naturally.
      meetings = meetings.slice().reverse();
      var combined = meetings.map(function (m) {
        return (m.home_score || 0) + (m.away_score || 0);
      });
      var labels = meetings.map(function (m) {
        var d = new Date(m.start_time);
        return isNaN(d) ? '?' : d.toLocaleString('en-GB', {day:'numeric', month:'short', year:'2-digit'});
      });
      new Chart(h2hCanvas, {
        type: 'line',
        data: {
          labels: labels,
          datasets: [{
            label: 'Combined goals',
            data: combined,
            fill: true,
            tension: 0.2,
            borderColor: '#3D7EAA',
            backgroundColor: 'rgba(61, 126, 170, 0.18)',
            pointRadius: 3,
          }],
        },
        options: {
          plugins: { legend: { display: false } },
          scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } },
        },
      });
    }
  }
})();
