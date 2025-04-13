const ctx = document.getElementById('crowdChart').getContext('2d');
const crowdChart = new Chart(ctx, {
  type: 'line',
  data: { labels: [], datasets: [{
    label: 'People Count',
    data: [],
    borderColor: 'rgba(0, 255, 255, 1)',
    backgroundColor: 'rgba(0, 255, 255, 0.2)',
    borderWidth: 3,
    tension: 0.4,
    fill: true,
    pointRadius: 4,
    pointHoverRadius: 6
  }]},
  options: {
    animation: { duration: 800, easing: 'easeOutQuart' },
    plugins: {
      legend: {
        labels: { color: '#ffffff', font: { size:14, weight:'bold' } }
      }
    },
    scales: {
      x: { ticks:{color:'#ffffff'}, grid:{color:'rgba(255,255,255,0.1)'} },
      y: { beginAtZero:true, ticks:{color:'#ffffff'}, grid:{color:'rgba(255,255,255,0.1)'} }
    }
  }
});

async function fetchCrowdData() {
  const res = await fetch('/crowd_data');
  const data = await res.json();
  const labels = data.map(d=>new Date(d.time*1000).toLocaleTimeString());
  const counts = data.map(d=>d.count);
  const latest = counts[counts.length-1]||0;
  document.getElementById('count-display').textContent = `People Count: ${latest}`;
  crowdChart.data.labels = labels;
  crowdChart.data.datasets[0].data = counts;
  crowdChart.update();
}

setInterval(fetchCrowdData, 1000);
