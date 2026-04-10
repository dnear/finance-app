// script.js
document.addEventListener('DOMContentLoaded', function() {
    initializeTheme();
    initializeLoadingUX();
    initializeGlobalSkeletonLoading();
    initializePaginationUX();
    initializeIOSModalFix();

    // Konfirmasi hapus dengan sweet alert style (opsional)
    const deleteLinks = document.querySelectorAll('.delete-confirm');
    deleteLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            if (!confirm('Apakah Anda yakin ingin menghapus? Data yang dihapus tidak dapat dikembalikan.')) {
                e.preventDefault();
                return;
            }

            const deleteUrl = this.getAttribute('data-delete-url') || this.getAttribute('href');
            if (deleteUrl) {
                window.location.href = deleteUrl;
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

    // Auto hide alert setelah 3 detik
    setTimeout(function() {
        const alerts = document.querySelectorAll('.flash-alert[data-auto-hide="true"]');
        alerts.forEach(alert => {
            if (typeof bootstrap !== 'undefined') {
                bootstrap.Alert.getOrCreateInstance(alert).close();
            } else {
                alert.remove();
            }
        });
    }, 3000);

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

function initializeLoadingUX() {
    document.querySelectorAll('form').forEach(function(form) {
        form.addEventListener('submit', function() {
            if (form.dataset.submitting === 'true') {
                return;
            }

            form.dataset.submitting = 'true';
            const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
            const originalText = submitBtn ? (submitBtn.dataset.originalText || submitBtn.innerHTML || submitBtn.value) : '';

            if (submitBtn) {
                submitBtn.dataset.originalText = originalText;
                submitBtn.disabled = true;
                submitBtn.classList.add('is-skeleton-loading');

                const btnText = submitBtn.querySelector('#btn-text');
                const btnLoading = submitBtn.querySelector('#btn-loading');
                if (btnText && btnLoading) {
                    btnText.style.display = 'none';
                    btnLoading.style.display = 'inline-flex';
                    btnLoading.setAttribute('aria-hidden', 'false');
                }

                // Fallback reset when submit fails without navigation (e.g. network issue)
                window.setTimeout(function () {
                    if (form.dataset.submitting !== 'true') {
                        return;
                    }

                    form.dataset.submitting = 'false';
                    submitBtn.disabled = false;
                    submitBtn.classList.remove('is-skeleton-loading');

                    if (btnText && btnLoading) {
                        btnText.style.display = 'inline';
                        btnLoading.style.display = 'none';
                        btnLoading.setAttribute('aria-hidden', 'true');
                    }
                }, 15000);
            }
        });
    });

    // Ensure UI state is reset when browser restores page from cache/history
    window.addEventListener('pageshow', function () {
        document.querySelectorAll('form[data-submitting="true"]').forEach(function (form) {
            form.dataset.submitting = 'false';
            const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
            if (!submitBtn) {
                return;
            }

            submitBtn.disabled = false;
            submitBtn.classList.remove('is-skeleton-loading');

            const btnText = submitBtn.querySelector('#btn-text');
            const btnLoading = submitBtn.querySelector('#btn-loading');
            if (btnText && btnLoading) {
                btnText.style.display = 'inline';
                btnLoading.style.display = 'none';
                btnLoading.setAttribute('aria-hidden', 'true');
            }
        });
    });
}

function initializeGlobalSkeletonLoading() {
    window.addEventListener('load', function () {
        setTimeout(function () {
            document.querySelectorAll("[id^='skeleton']").forEach(function (element) {
                element.style.display = 'none';
            });

            document.querySelectorAll("[id$='content']").forEach(function (element) {
                element.style.display = 'block';
            });
        }, 300);
    });
}

function initializePaginationUX() {
    const paginationLinks = document.querySelectorAll('[data-pagination-nav] a, .pagination-pill');

    paginationLinks.forEach(function(link) {
        link.addEventListener('click', function() {
            try {
                sessionStorage.setItem('finance-scroll-top', 'true');
            } catch (error) {
                // Ignore storage issues
            }
        });
    });

    try {
        if (sessionStorage.getItem('finance-scroll-top') === 'true') {
            sessionStorage.removeItem('finance-scroll-top');
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }
    } catch (error) {
        // Ignore storage issues
    }
}

function initializeIOSModalFix() {
    if (typeof bootstrap === 'undefined') {
        return;
    }

    let scrollY = 0;

    const lockBodyScroll = () => {
        if (document.body.dataset.modalScrollLock === 'true') {
            return;
        }

        scrollY = window.scrollY || window.pageYOffset || 0;
        document.body.dataset.modalScrollLock = 'true';
        document.body.style.top = `-${scrollY}px`;
        document.body.classList.add('modal-open');
    };

    const unlockBodyScroll = () => {
        if (document.querySelectorAll('.modal.show').length > 0) {
            return;
        }

        const storedTop = document.body.style.top;
        document.body.classList.remove('modal-open');
        document.body.style.top = '';
        delete document.body.dataset.modalScrollLock;

        const offset = storedTop ? Math.abs(parseInt(storedTop, 10)) : scrollY;
        window.scrollTo(0, Number.isNaN(offset) ? scrollY : offset);
    };

    document.querySelectorAll('.modal').forEach((modal) => {
        modal.addEventListener('show.bs.modal', lockBodyScroll);
        modal.addEventListener('shown.bs.modal', () => {
            modal.style.pointerEvents = 'auto';
            const content = modal.querySelector('.modal-content');
            if (content) {
                content.style.pointerEvents = 'auto';
            }
        });
        modal.addEventListener('hidden.bs.modal', unlockBodyScroll);
    });
}
