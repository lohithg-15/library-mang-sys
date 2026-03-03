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

function showBookEditForm(book, allBooks, tableDiv, resultDiv) {
    // Replace the table with the edit form
    const editFormHtml = `
        <div class="book-edit-row">
            <div class="edit-field">
                <label>Title:</label>
                <input type="text" id="edit-title" value="${escapeHtml(book.title)}" />
            </div>
            <div class="edit-field">
                <label>Author:</label>
                <input type="text" id="edit-author" value="${escapeHtml(book.author)}" />
            </div>
            <div class="edit-field">
                <label>Quantity:</label>
                <input type="number" id="edit-quantity" value="${book.quantity}" min="1" />
            </div>
            <div class="edit-field">
                <label>Shelf:</label>
                <input type="text" id="edit-shelf" value="${escapeHtml(book.shelf)}" />
            </div>
            <div class="edit-actions">
                <button class="btn-save-edit">💾 Save</button>
                <button class="btn-cancel-edit">❌ Cancel</button>
            </div>
        </div>
    `;
    tableDiv.innerHTML = editFormHtml;

    // Save button handler
    tableDiv.querySelector(".btn-save-edit").addEventListener("click", async () => {
        const title = document.getElementById("edit-title").value.trim();
        const author = document.getElementById("edit-author").value.trim();
        const quantity = document.getElementById("edit-quantity").value;
        const shelf = document.getElementById("edit-shelf").value.trim();

        if (title.length < 2 || author.length < 2 || quantity < 1 || !shelf) {
            resultDiv.innerHTML = "";
            resultDiv.appendChild(createMessage("❌ Please fill in all fields correctly", "error"));
            return;
        }

        resultDiv.innerHTML = "⏳ Updating...";

        const result = await updateBookDetails(book.id, title, author, quantity, shelf);

        resultDiv.innerHTML = "";

        if (result.success) {
            resultDiv.appendChild(createMessage("✅ Book updated successfully!", "success"));
            // Reload the books list
            setTimeout(() => {
                document.getElementById("loadBooksBtn").click();
            }, 1000);
        } else {
            resultDiv.appendChild(createMessage(`❌ ${result.error}`, "error"));
            // Show edit form again
            setTimeout(() => {
                showBookEditForm(book, allBooks, tableDiv, resultDiv);
            }, 1000);
        }
    });

    // Cancel button handler
    tableDiv.querySelector(".btn-cancel-edit").addEventListener("click", () => {
        // Reload the books list
        document.getElementById("loadBooksBtn").click();
    });
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

async function addBookManually(title, author, quantity, shelf) {
    try {
        const response = await fetch(`${API_URL}/add-book-manual/`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                ...getAuthHeaders()
            },
            body: JSON.stringify({
                title: title,
                author: author,
                quantity: parseInt(quantity),
                shelf: shelf
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Failed to add book");
        }

        return { success: true, data: data };
    } catch (error) {
        return { success: false, error: error.message };
    }
}

async function getBooksForEdit() {
    try {
        const response = await fetch(`${API_URL}/books-for-edit/`, {
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

async function updateBookDetails(bookId, title, author, quantity, shelf) {
    try {
        const response = await fetch(`${API_URL}/update-book/`, {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
                ...getAuthHeaders()
            },
            body: JSON.stringify({
                book_id: bookId,
                title: title,
                author: author,
                quantity: parseInt(quantity),
                shelf: shelf
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Failed to update book");
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

    // ===== TAB SWITCHING =====
    document.querySelectorAll(".tab-btn").forEach(btn => {
        btn.addEventListener("click", (e) => {
            // Remove active class from all tabs
            document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
            document.querySelectorAll(".tab-content").forEach(tc => tc.classList.remove("active"));
            
            // Add active class to clicked tab
            btn.classList.add("active");
            const tabId = btn.getAttribute("data-tab");
            const tabContent = document.getElementById(tabId);
            if (tabContent) {
                tabContent.classList.add("active");
                tabContent.style.display = "block";
            }
        });
    });

    // ===== MANUAL BOOK ENTRY =====
    document.getElementById("manualBookForm").addEventListener("submit", async (e) => {
        e.preventDefault();

        const resultDiv = document.getElementById("manualBookResult");
        resultDiv.innerHTML = "";

        const title = document.getElementById("manualTitle").value.trim();
        const author = document.getElementById("manualAuthor").value.trim();
        const quantity = document.getElementById("manualQuantity").value;
        const shelf = document.getElementById("manualShelf").value.trim();

        // Validate inputs
        if (title.length < 2) {
            resultDiv.appendChild(createMessage("❌ Title must be at least 2 characters", "error"));
            return;
        }
        if (author.length < 2) {
            resultDiv.appendChild(createMessage("❌ Author must be at least 2 characters", "error"));
            return;
        }
        if (quantity < 1) {
            resultDiv.appendChild(createMessage("❌ Quantity must be at least 1", "error"));
            return;
        }
        if (!shelf) {
            resultDiv.appendChild(createMessage("❌ Please enter a shelf location", "error"));
            return;
        }

        resultDiv.appendChild(createMessage("⏳ Adding book...", "loading"));

        const result = await addBookManually(title, author, quantity, shelf);

        if (result.success) {
            resultDiv.innerHTML = "";
            const card = document.createElement("div");
            card.className = "upload-result-card";
            card.innerHTML = `
                <div class="upload-result-header">
                    <span class="upload-result-success-icon">✅</span>
                    <h3>Book Added Successfully!</h3>
                </div>
                <div class="upload-result-details">
                    <div class="upload-detail-box">
                        <div class="upload-detail-label">📖 Title</div>
                        <div class="upload-detail-value">${escapeHtml(title)}</div>
                    </div>
                    <div class="upload-detail-box">
                        <div class="upload-detail-label">👤 Author</div>
                        <div class="upload-detail-value">${escapeHtml(author)}</div>
                    </div>
                    <div class="upload-detail-box">
                        <div class="upload-detail-label">📦 Quantity</div>
                        <div class="upload-detail-value">${quantity}</div>
                    </div>
                    <div class="upload-detail-box">
                        <div class="upload-detail-label">📍 Shelf</div>
                        <div class="upload-detail-value">${escapeHtml(shelf)}</div>
                    </div>
                </div>
            `;
            resultDiv.appendChild(card);
            document.getElementById("manualBookForm").reset();
        } else {
            resultDiv.appendChild(createMessage(`❌ ${result.error}`, "error"));
        }
    });

    // ===== MANAGE BOOKS =====
    document.getElementById("loadBooksBtn").addEventListener("click", async () => {
        const resultDiv = document.getElementById("manageBooksResult");
        const listDiv = document.getElementById("booksList");
        const tableDiv = document.getElementById("booksTable");

        resultDiv.innerHTML = "⏳ Loading books...";
        tableDiv.innerHTML = "";

        const result = await getBooksForEdit();

        resultDiv.innerHTML = "";

        if (result.success) {
            if (result.data.books.length === 0) {
                resultDiv.appendChild(createMessage("📭 No books in database", "info"));
                listDiv.style.display = "none";
            } else {
                listDiv.style.display = "block";
                const html = `
                    <table class="books-table">
                        <tr>
                            <th>Title</th>
                            <th>Author</th>
                            <th>Quantity</th>
                            <th>Shelf</th>
                            <th>Action</th>
                        </tr>
                        ${result.data.books.map(book => `
                            <tr>
                                <td>${escapeHtml(book.title)}</td>
                                <td>${escapeHtml(book.author)}</td>
                                <td>${book.quantity}</td>
                                <td>${escapeHtml(book.shelf)}</td>
                                <td><button class="book-edit-btn" data-id="${book.id}">✏️ Edit</button></td>
                            </tr>
                        `).join("")}
                    </table>
                `;
                tableDiv.innerHTML = html;

                // Add event listeners to edit buttons
                tableDiv.querySelectorAll(".book-edit-btn").forEach(btn => {
                    btn.addEventListener("click", (e) => {
                        const bookId = btn.getAttribute("data-id");
                        const book = result.data.books.find(b => b.id === parseInt(bookId));
                        if (book) {
                            showBookEditForm(book, result.data.books, tableDiv, resultDiv);
                        }
                    });
                });
            }
        } else {
            resultDiv.appendChild(createMessage(`❌ ${result.error}`, "error"));
            listDiv.style.display = "none";
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
