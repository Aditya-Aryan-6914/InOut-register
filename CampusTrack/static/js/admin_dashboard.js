(function () {
  "use strict";

  const POLL_INTERVAL_MS = 12000;

  const statActiveUsers = document.getElementById("statActiveUsers");
  const statCurrentlyIn = document.getElementById("statCurrentlyIn");
  const statCurrentlyOut = document.getElementById("statCurrentlyOut");
  const statTodayCheckins = document.getElementById("statTodayCheckins");
  const roomTable = document.getElementById("roomTable");

  function applyLiveCounts(data) {
    if (statActiveUsers) statActiveUsers.textContent = data.active_users;
    if (statCurrentlyIn) statCurrentlyIn.textContent = data.currently_in;
    if (statCurrentlyOut) statCurrentlyOut.textContent = data.currently_out;
    if (statTodayCheckins) statTodayCheckins.textContent = data.today_checkins;

    if (roomTable && Array.isArray(data.rooms)) {
      data.rooms.forEach(function (room) {
        const row = roomTable.querySelector('tr[data-room-id="' + room.id + '"]');
        if (!row) return;

        const inCell = row.querySelector(".ct-room-in-cell");
        if (inCell) inCell.textContent = room.currently_in;

        const lastCell = row.querySelector(".ct-room-last-cell");
        if (lastCell) {
          lastCell.textContent = room.last_checkin_at ? formatTimestamp(room.last_checkin_at) : "—";
        }
      });
    }
  }

  function formatTimestamp(isoString) {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return "—";
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" }) +
      ", " + d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  }

  function pollLiveCounts() {
    fetch(window.location.pathname + "/live-counts", { headers: { "Accept": "application/json" } })
      .then(function (res) { return res.ok ? res.json() : null; })
      .then(function (data) { if (data) applyLiveCounts(data); })
      .catch(function () { /* silently skip this tick; try again next interval */ });
  }

  // Only poll if the dashboard's stat cards are actually on this page.
  if (statActiveUsers) {
    setInterval(pollLiveCounts, POLL_INTERVAL_MS);
  }

  // ---------- reject with an optional reason ----------
  document.querySelectorAll(".ct-reject-form").forEach(function (form) {
    form.addEventListener("submit", function (evt) {
      const name = form.closest("tr").querySelector("td").textContent.trim();
      const reason = window.prompt("Reject " + name + "'s request. Reason (optional):");
      if (reason === null) {
        evt.preventDefault(); // user hit Cancel — abort the reject entirely
        return;
      }
      form.querySelector('input[name="reason"]').value = reason;
    });
  });
})();
