// script.js
document.addEventListener('DOMContentLoaded', function() {
    initializeTheme();

    // Konfirmasi hapus dengan sweet alert style (opsional)
    const deleteLinks = document.querySelectorAll('.delete-confirm');
    deleteLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            if (!confirm('Apakah Anda yakin ingin menghapus? Data yang dihapus tidak dapat dikembalikan.')) {
                e.preventDefault();
            }
        });
    });

    // Tooltip Bootstrap
    if (typeof bootstrap !== 'undefined') {
        var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }

    // Auto hide alert setelah 5 detik
    setTimeout(function() {
        const alerts = document.querySelectorAll('.alert');
        alerts.forEach(alert => {
            if (typeof bootstrap !== 'undefined') {
                bootstrap.Alert.getOrCreateInstance(alert).close();
            }
        });
    }, 5000);

    // Smooth scroll untuk anchor
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const targetSelector = this.getAttribute('href');
            if (!targetSelector || targetSelector === '#') return;
            const target = document.querySelector(targetSelector);
            if (!target) return;
            e.preventDefault();
            target.scrollIntoView({
                behavior: 'smooth'
            });
        });
    });

    // Tambahkan class loading saat submit form (opsional)
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function() {
            const submitBtn = this.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Loading...';
                submitBtn.disabled = true;
            }
        });
    });

    // Register Service Worker for PWA
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/static/js/sw.js')
            .then(registration => {
                console.log('Service Worker registered with scope:', registration.scope);
            })
            .catch(error => {
                console.log('Service Worker registration failed:', error);
            });
    }

    // Set local datetime inputs to browser timezone (WIB)
    setLocalDatetimeInputs();

    // Rupiah Currency Formatting for Amount Inputs
    initializeRupiahFormatting();
});

/**
 * New input-masking approach for Rupiah currency formatting
 * This approach prevents cursor jumping and maintains proper digit order
 */
function formatRupiah(input) {
    // Save cursor position relative to digits only
    const cursorPos = input.selectionStart;
    const oldValue = input.value;
    
    // Count digits before cursor in old value
    const digitsBeforeCursor = oldValue.slice(0, cursorPos).replace(/\D/g, '').length;
    
    // Strip everything except digits
    const digits = oldValue.replace(/\D/g, '');
    
    // Limit to reasonable max (15 digits)
    const limitedDigits = digits.slice(0, 15);
    
    // Format with dot thousand separator
    const formatted = limitedDigits.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    
    // Update display value
    input.value = formatted;
    
    // Update hidden input with raw number for form submission
    const hiddenInput = input.previousElementSibling || document.querySelector('input[name="amount_raw"]');
    if (hiddenInput && hiddenInput.type === 'hidden') {
        hiddenInput.value = limitedDigits;
    }
    
    // Restore cursor: count forward through formatted string until we've
    // passed digitsBeforeCursor digits
    let digitCount = 0;
    let newCursorPos = 0;
    for (let i = 0; i < formatted.length; i++) {
        if (/\d/.test(formatted[i])) digitCount++;
        if (digitCount === digitsBeforeCursor) {
            newCursorPos = i + 1;
            break;
        }
    }
    // If cursor was at end or past all digits
    if (digitsBeforeCursor === 0) newCursorPos = 0;
    if (digitCount < digitsBeforeCursor) newCursorPos = formatted.length;
    
    input.setSelectionRange(newCursorPos, newCursorPos);
}

/**
 * Initialize Rupiah currency formatting using event delegation
 */
function initializeRupiahFormatting() {
    // Use event delegation to handle all amount inputs
    document.addEventListener('input', function(e) {
        if (e.target.matches('input[data-rupiah]')) {
            formatRupiah(e.target);
        }
    });
}

/**
 * Set datetime-local inputs to browser local time (WIB)
 */
function setLocalDatetimeInputs() {
    const now = new Date();
    const offset = now.getTimezoneOffset() * 60000;
    const localISO = new Date(now - offset).toISOString().slice(0, 16);
    document.querySelectorAll('input[type="datetime-local"]').forEach(function(input) {
        if (!input.value) {
            input.value = localISO;
        }
    });
}

function initializeTheme() {
    const storageKey = 'finance-theme';
    const root = document.documentElement;
    const themeButtons = document.querySelectorAll('[data-theme-toggle]');
    const metaTheme = document.getElementById('theme-color-meta');
    const mediaQuery = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;

    const getSystemTheme = () => (mediaQuery && mediaQuery.matches ? 'dark' : 'light');

    const setTheme = (theme) => {
        root.setAttribute('data-theme', theme);
        if (metaTheme) {
            metaTheme.setAttribute('content', theme === 'dark' ? '#0f172a' : '#3b82f6');
        }
        themeButtons.forEach((btn) => {
            const icon = btn.querySelector('i');
            if (icon) {
                icon.className = theme === 'dark' ? 'bi bi-sun-fill' : 'bi bi-moon-stars-fill';
            }
            btn.setAttribute('aria-label', theme === 'dark' ? 'Gunakan mode terang' : 'Gunakan mode gelap');
            btn.setAttribute('title', theme === 'dark' ? 'Mode terang' : 'Mode gelap');
        });
    };

    const storedTheme = localStorage.getItem(storageKey);
    setTheme(storedTheme || root.getAttribute('data-theme') || getSystemTheme());

    themeButtons.forEach((btn) => {
        btn.addEventListener('click', () => {
            const currentTheme = root.getAttribute('data-theme') || getSystemTheme();
            const nextTheme = currentTheme === 'dark' ? 'light' : 'dark';
            localStorage.setItem(storageKey, nextTheme);
            setTheme(nextTheme);
        });
    });

    if (mediaQuery && !storedTheme) {
        const onSystemThemeChange = (e) => setTheme(e.matches ? 'dark' : 'light');
        if (typeof mediaQuery.addEventListener === 'function') {
            mediaQuery.addEventListener('change', onSystemThemeChange);
        } else if (typeof mediaQuery.addListener === 'function') {
            mediaQuery.addListener(onSystemThemeChange);
        }
    }
}

// ===== PAGE LOADING INDICATOR =====
(function() {
    const loader = document.getElementById('page-loader');
    const overlay = document.getElementById('submit-overlay');

    if (!loader && !overlay) return;

    // Show loading bar on page navigation
    document.addEventListener('click', function(e) {
        const link = e.target.closest('a[href]');
        if (!link) return;
        const href = link.getAttribute('href');
        if (!href || href.startsWith('#') || href.startsWith('javascript')) return;
        if (link.getAttribute('data-bs-toggle')) return;
        if (link.getAttribute('target') === '_blank') return;
        if (link.hostname && link.hostname !== location.hostname) return;

        // Show loading bar
        if (loader) {
            loader.style.display = 'block';
            loader.style.width = '0%';
            setTimeout(() => { loader.style.width = '70%'; }, 50);
            setTimeout(() => { loader.style.width = '90%'; }, 500);
        }
    });

    // Show spinner on form submission
    document.addEventListener('submit', function(e) {
        const form = e.target;
        // Skip search/filter forms (GET method)
        if (form.method && form.method.toLowerCase() === 'get') return;
        if (!overlay) return;
        overlay.style.display = 'flex';
        // Change text based on action
        const submitBtn = form.querySelector('[type="submit"]');
        if (submitBtn) {
            const action = submitBtn.textContent.trim();
            const msgEl = overlay.querySelector('.mt-2');
            if (action.includes('Hapus') || action.includes('hapus')) {
                msgEl.textContent = 'Menghapus...';
            } else if (action.includes('Simpan') || action.includes('simpan')) {
                msgEl.textContent = 'Menyimpan...';
            } else {
                msgEl.textContent = 'Memproses...';
            }
        }
    });

    // Hide everything when page is fully loaded
    window.addEventListener('pageshow', function() {
        if (loader) {
            loader.style.width = '100%';
            setTimeout(() => {
                loader.style.display = 'none';
                loader.style.width = '0%';
            }, 300);
        }
        if (overlay) overlay.style.display = 'none';
    });

    // Hide overlay if back button pressed
    window.addEventListener('popstate', function() {
        if (overlay) overlay.style.display = 'none';
    });
})();
