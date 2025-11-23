const chatWindow = document.getElementById("chat-window");
const imageInput = document.getElementById("image-input");
const sendBtn = document.getElementById("send-btn");

// Chatbot elements
const chatInput = document.getElementById("chat-input");
const chatSendBtn = document.getElementById("chat-send-btn");

// Camera elements (make sure these exist in index.html)
const cameraBtn = document.getElementById("camera-btn");
const captureBtn = document.getElementById("capture-btn");
const cameraPreview = document.getElementById("camera-preview");
const captureCanvas = document.getElementById("capture-canvas");

let lastLocation = { lat: null, lng: null };
let lastDetectedClass = null;   // e.g. "Battery", "Mobile"
let lastDetectedName = null;    // e.g. "Battery", "Mobile Phone"
let cameraStream = null;

// --------- LOCATION (for nearest recycling centre) ---------
if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
        pos => {
            lastLocation.lat = pos.coords.latitude;
            lastLocation.lng = pos.coords.longitude;
        },
        err => {
            console.warn("Location error:", err.message);
        }
    );
}

// --------- CHAT WINDOW HELPERS ---------
function addMessage(sender, content, isHtml = false) {
    const div = document.createElement("div");
    div.classList.add("message", sender);
    div.innerHTML = isHtml ? content : escapeHtml(content);
    chatWindow.appendChild(div);
    chatWindow.scrollTop = chatWindow.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.innerText = text;
    return div.innerHTML;
}

// --------- COMMON IMAGE ANALYSIS FUNCTION ---------
function analyzeFile(file) {
    if (!file) {
        alert("No image selected or captured.");
        return;
    }

    // Show user image as a chat bubble
    const reader = new FileReader();
    reader.onload = e => {
        const imgHtml = `<div class="user-image"><img src="${e.target.result}" alt="uploaded"></div>`;
        addMessage("user", imgHtml, true);
    };
    reader.readAsDataURL(file);

    const formData = new FormData();
    formData.append("image", file);
    if (lastLocation.lat && lastLocation.lng) {
        formData.append("lat", lastLocation.lat);
        formData.append("lng", lastLocation.lng);
    }

    addMessage("bot", "Analyzing the image...");

    fetch("/analyze", {
        method: "POST",
        body: formData
    })
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                addMessage("bot", "Error: " + data.error);
                return;
            }

            // Remember last detection for chatbot context
            lastDetectedClass = data.predicted_class;
            lastDetectedName  = data.product_name;

            let html = `Detected: <b>${data.product_name}</b><br>`;
            html += `Class: ${data.predicted_class} (confidence: ${(data.confidence * 100).toFixed(1)}%)<br>`;
            html += `Category: <b>${data.category}</b><br><br>`;

            if (data.disposal_steps && data.disposal_steps.length > 0) {
                html += "<b>How to dispose:</b><ul>";
                data.disposal_steps.forEach(step => {
                    html += `<li>${step}</li>`;
                });
                html += "</ul>";
            }

            if (data.hazards) {
                html += `<b>Hazards:</b> ${data.hazards}<br>`;
            }
            if (data.tips) {
                html += `<b>Tips:</b> ${data.tips}<br>`;
            }

            if (data.nearest_recycling_link) {
                html += `<br><a href="${data.nearest_recycling_link}" target="_blank">
                           Find nearest recycling centre
                         </a>`;
            }

            addMessage("bot", html, true);
        })
        .catch(err => {
            console.error(err);
            addMessage("bot", "Something went wrong while analyzing the image.");
        });
}

// --------- UPLOAD BUTTON HANDLER ---------
sendBtn.addEventListener("click", () => {
    const file = imageInput.files[0];
    if (!file) {
        alert("Please select or capture an image first.");
        return;
    }
    analyzeFile(file);
});

// --------- CAMERA: OPEN & CAPTURE ---------
if (cameraBtn && captureBtn && cameraPreview && captureCanvas) {

    cameraBtn.addEventListener("click", async () => {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            alert("Camera not supported in this browser.");
            return;
        }

        try {
            cameraStream = await navigator.mediaDevices.getUserMedia({ video: true });
            cameraPreview.srcObject = cameraStream;
            cameraPreview.style.display = "block";
            captureBtn.style.display = "inline-block";
            cameraBtn.disabled = true; // prevent reopening multiple times
        } catch (err) {
            console.error("Error accessing camera:", err);
            alert("Could not access camera. Please check permissions.");
        }
    });

    captureBtn.addEventListener("click", () => {
        if (!cameraStream) {
            alert("Camera is not active.");
            return;
        }

        const videoTrack = cameraStream.getVideoTracks()[0];
        const settings = videoTrack.getSettings();
        const width = settings.width || 640;
        const height = settings.height || 480;

        captureCanvas.width = width;
        captureCanvas.height = height;

        const ctx = captureCanvas.getContext("2d");
        ctx.drawImage(cameraPreview, 0, 0, width, height);

        // Convert canvas image to Blob -> File -> analyze
        captureCanvas.toBlob(blob => {
            if (!blob) {
                alert("Could not capture image.");
                return;
            }
            const file = new File([blob], "camera_capture.jpg", { type: "image/jpeg" });
            analyzeFile(file);
        }, "image/jpeg", 0.9);
    });

    // Stop camera when leaving page
    window.addEventListener("beforeunload", () => {
        if (cameraStream) {
            cameraStream.getTracks().forEach(t => t.stop());
        }
    });
}

// --------- CHATBOT TEXT Q&A ---------
chatSendBtn.addEventListener("click", () => {
    const message = chatInput.value.trim();
    if (!message) {
        return;
    }

    // Show user message in chat
    addMessage("user", message);
    chatInput.value = "";

    // Prepare payload for backend
    const payload = {
        message: message,
        last_class: lastDetectedClass,
        last_name: lastDetectedName
    };

    fetch("/chat", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
    })
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                addMessage("bot", "Error: " + data.error);
                return;
            }
            addMessage("bot", data.reply, true);
        })
        .catch(err => {
            console.error(err);
            addMessage("bot", "Something went wrong while answering your question.");
        });
});

// Optional: allow Enter key to send question
chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        chatSendBtn.click();
    }
});
