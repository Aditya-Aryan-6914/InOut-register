(function () {
  "use strict";

  document.querySelectorAll(".ct-set-location-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      if (!("geolocation" in navigator)) {
        window.alert("Your browser doesn't support geolocation. Try a different device to set this room's location.");
        return;
      }

      const card = btn.closest(".ct-room-card");
      const roomId = card.dataset.roomId;
      const statusEl = card.querySelector(".ct-room-location-status");

      const radiusInput = window.prompt(
        "Geofence radius in meters (how far from this exact spot a check-in is still allowed). Default 100:",
        "100"
      );
      if (radiusInput === null) return; // cancelled
      const radius = parseInt(radiusInput, 10) || 100;

      btn.disabled = true;
      btn.textContent = "Getting location…";

      navigator.geolocation.getCurrentPosition(
        function (position) {
          fetch(`/admin/rooms/${roomId}/set-location`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              latitude: position.coords.latitude,
              longitude: position.coords.longitude,
              radius_m: radius,
            }),
          })
            .then(function (res) { return res.json().then(function (data) { return { ok: res.ok, data: data }; }); })
            .then(function (result) {
              btn.disabled = false;
              if (result.ok && result.data.success) {
                btn.textContent = "Update location";
                statusEl.innerHTML =
                  '<span class="ct-location-set">📍 Location set (±' + result.data.radius_m + 'm)</span>';
              } else {
                btn.textContent = "Set location";
                window.alert(result.data.error || "Couldn't save the location. Please try again.");
              }
            })
            .catch(function () {
              btn.disabled = false;
              btn.textContent = "Set location";
              window.alert("Couldn't reach the server. Check your connection and try again.");
            });
        },
        function (error) {
          btn.disabled = false;
          btn.textContent = "Set location";
          window.alert(
            "Couldn't get your location: " + error.message +
            ". Make sure location access is allowed for this site."
          );
        },
        { enableHighAccuracy: true, timeout: 10000 }
      );
    });
  });
})();
