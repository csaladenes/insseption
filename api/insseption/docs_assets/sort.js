
document.querySelectorAll('table.sortable').forEach(function (table) {
  var heads = table.tHead ? table.tHead.rows[0].cells : [];
  Array.prototype.forEach.call(heads, function (th, col) {
    th.title = 'Sort';
    th.addEventListener('click', function () {
      var asc = th.getAttribute('aria-sort') !== 'ascending';
      Array.prototype.forEach.call(heads, function (h) { h.removeAttribute('aria-sort'); });
      th.setAttribute('aria-sort', asc ? 'ascending' : 'descending');
      var body = table.tBodies[0], rows = Array.prototype.slice.call(body.rows);
      var key = function (r) {
        var c = r.cells[col];
        return c ? (c.hasAttribute('data-v') ? c.getAttribute('data-v') : c.textContent.trim()) : '';
      };
      rows.sort(function (a, b) {
        var x = key(a), y = key(b), nx = Number(x), ny = Number(y);
        var cmp = (x !== '' && y !== '' && !isNaN(nx) && !isNaN(ny)) ? nx - ny
                  : x.localeCompare(y, undefined, {numeric: true, sensitivity: 'base'});
        return asc ? cmp : -cmp;
      });
      rows.forEach(function (r) { body.appendChild(r); });
    });
  });
});
document.querySelectorAll('.cards [data-filter]').forEach(function (card) {
  card.addEventListener('click', function () {
    var f = card.getAttribute('data-filter'), on = !card.classList.contains('on');
    document.querySelectorAll('.cards [data-filter]').forEach(function (c) { c.classList.remove('on'); });
    if (on) card.classList.add('on');
    document.querySelectorAll('table[data-filterable] tbody tr').forEach(function (r) {
      r.style.display = (!on || r.classList.contains(f)) ? '' : 'none';
    });
  });
});
