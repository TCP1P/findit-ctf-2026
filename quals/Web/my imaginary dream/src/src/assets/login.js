(function () {
  var frame = document.getElementById("login-bg-video-frame");
  var permissionGranted = false;
  var playerStarted = false;
  var overlay = document.getElementById("media-permission-overlay");
  var status = document.getElementById("media-permission-status");
  var toggle = document.getElementById("bg-audio-toggle");
  var submitBtn = document.getElementById("login-submit");
  var loginForm = document.querySelector("form");
  var playerSrc = frame ? frame.getAttribute("data-player-src") : null;

  function sendCommand(command, args) {
    if (!frame || !frame.contentWindow) {
      return;
    }
    frame.contentWindow.postMessage(
      JSON.stringify({
        event: "command",
        func: command,
        args: args || []
      }),
      "*"
    );
  }

  function startPlayer() {
    if (!frame || !playerSrc) {
      return;
    }

    if (!playerStarted) {
      frame.src = playerSrc + "&autoplay=1&mute=0";
      playerStarted = true;
    }

    sendCommand("unMute");
    sendCommand("setVolume", [100]);
    sendCommand("playVideo");
  }

  function grantPermission() {
    if (permissionGranted) {
      return;
    }

    permissionGranted = true;

    if (status) {
      status.textContent = "Permission granted. You may continue to login.";
    }
    if (overlay) {
      overlay.classList.add("permission-overlay--hidden");
    }
    if (submitBtn) {
      submitBtn.disabled = false;
    }

    startPlayer();
    if (status) {
      status.textContent = "Permission granted. You may continue to login.";
    }
    maybeAutoSubmit();
  }

  function maybeAutoSubmit() {
    if (!permissionGranted || !submitBtn || !loginForm) {
      return;
    }

    var username = document.getElementById("username");
    var password = document.getElementById("password");
    if (!username || !password) {
      return;
    }

    if (!username.value || !password.value) {
      return;
    }

    if (loginForm.requestSubmit) {
      loginForm.requestSubmit(submitBtn);
      return;
    }

    submitBtn.click();
  }

  function preventSubmit(event) {
    if (!permissionGranted) {
      event.preventDefault();
      if (status) {
        status.textContent = "Grant background audio permission first.";
      }
    }
  }

  if (toggle) {
    toggle.addEventListener("click", grantPermission, false);
  }
  if (submitBtn) {
    submitBtn.addEventListener("click", preventSubmit, false);
  }
  if (loginForm) {
    loginForm.addEventListener("submit", preventSubmit, false);
  }
})();
