const API_URL = "http://127.0.0.1:8000";

// Global state
let appState = {
    token: null,
    user: null,
    userRole: null,
    backendStatus: { running: false, authReady: false, ocrReady: false }
};

// ====================== AUTHENTICATION ======================

function saveToken(token) {
    localStorage.setItem("access_token", token);
    appState.token = token;
}

function getToken() {
    return localStorage.getItem("access_token");
}

function clearAuth() {
    localStorage.removeItem("access_token");
    appState.token = null;
    appState.user = null;
    appState.userRole = null;
}

async function login(username, password) {
    try {
        const formData = new FormData();
        formData.append("username", username);
        formData.append("password", password);

        const response = await fetch(`${API_URL}/auth/login/`, {
            method: "POST",
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Login failed");
        }

        // Save token and user info
        saveToken(data.access_token);
        appState.user = data.user;
        appState.userRole = data.user.role;

        return { success: true, user: data.user };
    } catch (error) {
        return { success: false, error: error.message };
    }
}

async function loginAsCustomer() {
    appState.userRole = "customer";
    appState.user = { username: "Guest Customer", role: "customer" };
    return { success: true, user: appState.user };
}

async function logout() {
    clearAuth();
    showLoginPage();
}

// ====================== UI FUNCTIONS ======================

function showLoginPage() {
    document.getElementById("loginContainer").style.display = "block";
    document.getElementById("appContainer").style.display = "none";
}

function showAppPage() {
    document.getElementById("loginContainer").style.display = "none";
    document.getElementById("appContainer").style.display = "block";

    // Show/hide sections based on role
    const adminSection = document.getElementById("adminSection");
    const customerSection = document.getElementById("customerSection");

    if (appState.userRole === "admin") {
        adminSection.style.display = "block";
    } else {
        adminSection.style.display = "none";
    }
    customerSection.style.display = "block";

    // Update header
    const roleEl = document.getElementById("userRole");
    const nameEl = document.getElementById("userName");

    if (appState.userRole === "admin") {
        roleEl.textContent = "🏪 Admin";
        roleEl.className = "user-badge admin";
        // Show username in a nice format, capitalize first letter
        const username = appState.user.username || "User";
        const displayName = username.charAt(0).toUpperCase() + username.slice(1);
        nameEl.textContent = displayName;
    } else {
        roleEl.textContent = "👤 Customer";
        roleEl.className = "user-badge customer";
        nameEl.textContent = "Guest";
    }
}

function escapeHtml(str) {
    if (str == null || str === undefined) return "";
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function createMessage(text, type) {
    const msgDiv = document.createElement("div");
    msgDiv.className = `message ${type}-message`;
    msgDiv.innerHTML = text;
    return msgDiv;
}

// ====================== BACKEND STATUS ======================

async function checkBackendStatus() {
    try {
        const response = await fetch(`${API_URL}/status/`);
        const data = await response.json();

        appState.backendStatus = {
            running: data.backend_running,
            authReady: data.auth_ready,
            ocrReady: data.ocr_ready
        };

        updateStatusIndicator();
    } catch (error) {
        appState.backendStatus.running = false;
        updateStatusIndicator();
    }
}

function updateStatusIndicator() {
    const statusDiv = document.getElementById("backendStatus");
    if (!statusDiv) return;

    if (!appState.backendStatus.running) {
        statusDiv.innerHTML = "❌ Backend Offline";
        statusDiv.className = "status-indicator offline";
    } else if (!appState.backendStatus.ocrReady) {
        statusDiv.innerHTML = "⏳ Initializing OCR...";
        statusDiv.className = "status-indicator initializing";
    } else {
        statusDiv.innerHTML = "✅ Backend Ready";
        statusDiv.className = "status-indicator ready";
    }
}

// ====================== API CALLS WITH AUTH ======================

function getAuthHeaders() {
    return {
        "Authorization": `Bearer ${appState.token}`
    };
}

async function uploadBook(image, quantity, shelf) {
    try {
        if (!appState.backendStatus.ocrReady) {
            throw new Error("Backend OCR not ready. Please wait...");
        }

        const formData = new FormData();
        formData.append("image", image);
        formData.append("quantity", quantity);
        formData.append("shelf", shelf);

        const response = await fetch(`${API_URL}/upload-book/`, {
            method: "POST",
            headers: getAuthHeaders(),
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || data.error || "Upload failed");
        }

        return { success: true, data: data };
    } catch (error) {
        return { success: false, error: error.message };
    }
}

async function searchBooks(query) {
    try {
        const response = await fetch(`${API_URL}/search-book/?query=${encodeURIComponent(query)}`);
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Search failed");
        }

        return { success: true, data: data };
    } catch (error) {
        return { success: false, error: error.message };
    }
}

async function debugAllBooks() {
    try {
        const response = await fetch(`${API_URL}/debug/all-books/`, {
            headers: getAuthHeaders()
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Failed to fetch books");
        }

        return { success: true, data: data };
    } catch (error) {
        return { success: false, error: error.message };
    }
}

async function resetDatabase() {
    try {
        const response = await fetch(`${API_URL}/debug/reset-database/`, {
            method: "POST",
            headers: getAuthHeaders()
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Reset failed");
        }

        return { success: true, data: data };
    } catch (error) {
        return { success: false, error: error.message };
    }
}

async function listUsers() {
    try {
        const response = await fetch(`${API_URL}/debug/list-users/`, {
            headers: getAuthHeaders()
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Failed to fetch users");
        }

        return { success: true, data: data };
    } catch (error) {
        return { success: false, error: error.message };
    }
}

// ====================== EVENT LISTENERS ======================

document.addEventListener("DOMContentLoaded", () => {
    checkBackendStatus();
    setInterval(checkBackendStatus, 5000);

    // Role selector buttons
    document.querySelectorAll(".role-btn").forEach(btn => {
        btn.addEventListener("click", (e) => {
            document.querySelectorAll(".role-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");

            const role = btn.dataset.role;
            document.getElementById("credentialsSection").style.display = role === "admin" ? "block" : "none";
            document.getElementById("customerLoginSection").style.display = role === "customer" ? "block" : "none";
        });
    });

    // Login form
    document.getElementById("authForm").addEventListener("submit", async (e) => {
        e.preventDefault();

        const username = document.getElementById("username").value;
        const password = document.getElementById("password").value;

        const result = await login(username, password);

        if (result.success) {
            showAppPage();
        } else {
            const errorDiv = document.getElementById("loginError");
            errorDiv.textContent = result.error;
            errorDiv.style.display = "block";
        }
    });

    // Customer button
    document.getElementById("customerBtn").addEventListener("click", async () => {
        const result = await loginAsCustomer();
        if (result.success) {
            showAppPage();
        }
    });

    // Logout button
    document.getElementById("logoutBtn").addEventListener("click", logout);

    // ===== ADMIN UPLOAD =====
    document.getElementById("uploadForm").addEventListener("submit", async (e) => {
        e.preventDefault();

        const resultDiv = document.getElementById("uploadResult");
        resultDiv.innerHTML = "";

        const image = document.getElementById("image").files[0];
        const quantity = document.getElementById("quantity").value;
        const shelf = document.getElementById("shelf").value;

        if (!image) {
            resultDiv.appendChild(createMessage("❌ Please select an image", "error"));
            return;
        }

        resultDiv.appendChild(createMessage("⏳ Uploading and extracting...", "loading"));

        const result = await uploadBook(image, quantity, shelf);

        if (result.success) {
            resultDiv.innerHTML = "";
            const card = document.createElement("div");
            card.className = "upload-result-card";
            card.innerHTML = `
                <div class="upload-result-header">
                    <span class="upload-result-success-icon">✅</span>
                    <h3>Book Uploaded Successfully!</h3>
                </div>
                <div class="upload-result-details">
                    <div class="upload-detail-box">
                        <div class="upload-detail-label">📖 Title</div>
                        <div class="upload-detail-value">${result.data.title}</div>
                    </div>
                    <div class="upload-detail-box">
                        <div class="upload-detail-label">👤 Author</div>
                        <div class="upload-detail-value">${result.data.author}</div>
                    </div>
                    <div class="upload-detail-box">
                        <div class="upload-detail-label">📦 Quantity</div>
                        <div class="upload-detail-value">${quantity}</div>
                    </div>
                    <div class="upload-detail-box">
                        <div class="upload-detail-label">📍 Shelf</div>
                        <div class="upload-detail-value">${shelf}</div>
                    </div>
                </div>
            `;
            resultDiv.appendChild(card);
            document.getElementById("uploadForm").reset();
        } else {
            resultDiv.appendChild(createMessage(`❌ ${result.error}`, "error"));
        }
    });

    // Clear upload button
    document.getElementById("clearUploadBtn").addEventListener("click", () => {
        document.getElementById("uploadForm").reset();
    });

    // ===== CUSTOMER SEARCH =====
    document.getElementById("searchBtn").addEventListener("click", async () => {
        const query = document.getElementById("searchQuery").value;
        const resultDiv = document.getElementById("searchResult");
        resultDiv.innerHTML = "";

        if (!query.trim()) {
            resultDiv.appendChild(createMessage("❌ Please enter a search query", "error"));
            return;
        }

        resultDiv.appendChild(createMessage("🔍 Searching...", "loading"));

        const result = await searchBooks(query);

        resultDiv.innerHTML = "";

        if (result.success) {
            if (result.data.count === 0) {
                resultDiv.appendChild(createMessage("📭 No books found", "info"));
            } else {
                // Show "Did you mean?" when fuzzy match was used (typo-tolerant search)
                if (result.data.did_you_mean) {
                    const didYouMeanDiv = document.createElement("div");
                    didYouMeanDiv.className = "did-you-mean";
                    didYouMeanDiv.innerHTML = `🔎 Did you mean: <strong>${escapeHtml(result.data.did_you_mean)}</strong>?`;
                    resultDiv.appendChild(didYouMeanDiv);
                }
                const booksDiv = document.createElement("div");
                booksDiv.className = "books-list";

                result.data.books.forEach(book => {
                    const bookCard = document.createElement("div");
                    bookCard.className = "book-card";
                    bookCard.innerHTML = `
                        <div class="book-header">
                            <h3>${escapeHtml(book.title)}</h3>
                            <span class="book-qty">Qty: ${book.quantity}</span>
                        </div>
                        <p><strong>Author:</strong> ${escapeHtml(book.author)}</p>
                        <p><strong>Location:</strong> Shelf ${escapeHtml(book.shelf)}</p>
                    `;
                    booksDiv.appendChild(bookCard);
                });

                resultDiv.appendChild(booksDiv);
            }
        } else {
            resultDiv.appendChild(createMessage(`❌ ${result.error}`, "error"));
        }
    });

    // Search on Enter key
    document.getElementById("searchQuery").addEventListener("keypress", (e) => {
        if (e.key === "Enter") {
            document.getElementById("searchBtn").click();
        }
    });

    // ===== ADMIN DEBUG BUTTONS =====
    document.getElementById("debugBtn").addEventListener("click", async () => {
        const resultDiv = document.getElementById("debugResult");
        resultDiv.innerHTML = "⏳ Loading...";

        const result = await debugAllBooks();

        resultDiv.innerHTML = "";

        if (result.success) {
            const html = `
                <h4>📚 Total Books: ${result.data.total_books}</h4>
                <table class="debug-table">
                    <tr>
                        <th>Title</th>
                        <th>Author</th>
                        <th>Qty</th>
                        <th>Shelf</th>
                    </tr>
                    ${result.data.books.map(b => `
                        <tr>
                            <td>${b.title}</td>
                            <td>${b.author}</td>
                            <td>${b.quantity}</td>
                            <td>${b.shelf}</td>
                        </tr>
                    `).join("")}
                </table>
            `;
            resultDiv.innerHTML = html;
        } else {
            resultDiv.appendChild(createMessage(`❌ ${result.error}`, "error"));
        }
    });

    document.getElementById("resetDbBtn").addEventListener("click", async () => {
        if (confirm("⚠️ Are you sure? This will delete ALL books!")) {
            const result = await resetDatabase();

            const resultDiv = document.getElementById("debugResult");
            resultDiv.innerHTML = "";

            if (result.success) {
                resultDiv.appendChild(createMessage("✅ Database reset successfully", "success"));
            } else {
                resultDiv.appendChild(createMessage(`❌ ${result.error}`, "error"));
            }
        }
    });

    document.getElementById("listUsersBtn").addEventListener("click", async () => {
        const resultDiv = document.getElementById("debugResult");
        resultDiv.innerHTML = "⏳ Loading...";

        const result = await listUsers();

        resultDiv.innerHTML = "";

        if (result.success) {
            const html = `
                <h4>👥 Total Users: ${result.data.total_users}</h4>
                <table class="debug-table">
                    <tr>
                        <th>Username</th>
                        <th>Role</th>
                        <th>Created</th>
                    </tr>
                    ${result.data.users.map(u => `
                        <tr>
                            <td>${u.username}</td>
                            <td><span class="role-badge ${u.role}">${u.role}</span></td>
                            <td>${new Date(u.created_at).toLocaleDateString()}</td>
                        </tr>
                    `).join("")}
                </table>
            `;
            resultDiv.innerHTML = html;
        } else {
            resultDiv.appendChild(createMessage(`❌ ${result.error}`, "error"));
        }
    });

    // Initialize
    const token = getToken();
    if (token) {
        appState.token = token;
        showAppPage();
    } else {
        showLoginPage();
    }
});
