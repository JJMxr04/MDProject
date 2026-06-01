(function () {
  const node = document.getElementById('equity-curve-data');
  if (!node) return;
  const data = JSON.parse(node.textContent);
  const canvas = document.getElementById('equity-curve');
  if (!canvas) return;
  // Sequential bet number on the x-axis keeps the chart readable even
  // when bets cluster on a single day.
  const labels = data.map((_, i) => i + 1);
  const series = data.map(d => d.cumulative_pl);
  new Chart(canvas, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [{
        label: 'Cumulative P/L',
        data: series,
        fill: true,
        tension: 0.15,
        borderColor: '#3D7EAA',
        backgroundColor: 'rgba(61, 126, 170, 0.15)',
        pointRadius: 2,
      }],
    },
    options: {
      plugins: { legend: { display: false } },
      scales: {
        x: { title: { display: true, text: 'Bet #' } },
        y: { title: { display: true, text: 'Cumulative P/L' } },
      },
    },
  });
})();
