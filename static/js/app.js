/**
 * app.js - Vanilla JavaScript client logic for SpendSmart Personal Expense Tracker
 * ==============================================================================
 * Handles:
 * - Live clock updating every second on Login page
 * - Client-side form validation with instant inline error display
 * - Smooth count-up animations for summary metric cards
 * - Category switching & Needs/Wants toggle on transaction form
 * - Mobile hamburger menu toggle
 * - Auto-dismissing toast notifications
 * - Accessible delete confirmation dialog
 * - Ripple effect on buttons
 */

document.addEventListener('DOMContentLoaded', () => {
  'use strict';

  // 1. Live Clock on Login Page
  initLiveClock();

  // 2. Client-side Login Validation & Button Ripple
  initLoginValidation();

  // 3. Count-up Animation for Dashboard Metrics
  initCountUp();

  // 4. Mobile Hamburger Menu Toggle
  initMobileMenu();

  // 5. Toast Auto-Dismiss
  initToasts();

  // 6. Delete Confirmation Modal
  initDeleteModal();

  // 7. Transaction Form Category & Needs/Wants Dynamic Switcher
  initTransactionForm();
});

/**
 * 1. Live Clock on Login Page
 * Displays formatted date & time: "Friday, 16 October 2026 · 03:42:17 PM"
 */
function initLiveClock() {
  const clockElement = document.getElementById('liveClockDisplay');
  if (!clockElement) return;

  function updateClock() {
    const now = new Date();

    const options = {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      year: 'numeric'
    };
    const datePart = now.toLocaleDateString('en-IN', options);

    let hours = now.getHours();
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const seconds = String(now.getSeconds()).padStart(2, '0');
    const ampm = hours >= 12 ? 'PM' : 'AM';
    hours = hours % 12 || 12;
    const hoursStr = String(hours).padStart(2, '0');
    const timePart = `${hoursStr}:${minutes}:${seconds} ${ampm}`;

    clockElement.textContent = `${datePart} · ${timePart}`;
  }

  updateClock();
  setInterval(updateClock, 1000);
}

/**
 * 2. Client-side Form Validation for Login Page
 */
function initLoginValidation() {
  const loginForm = document.getElementById('loginForm');
  if (!loginForm) return;

  const nameInput = document.getElementById('fullNameInput');
  const emailInput = document.getElementById('emailInput');
  const phoneInput = document.getElementById('phoneInput');

  function validateField(input, testFn, errorMsg) {
    const group = input.closest('.form-group');
    if (!group) return true;
    let feedback = group.querySelector('.invalid-feedback');

    const isValid = testFn(input.value.trim());
    if (!isValid) {
      input.classList.add('is-invalid');
      if (!feedback) {
        feedback = document.createElement('div');
        feedback.className = 'invalid-feedback';
        group.appendChild(feedback);
      }
      feedback.innerHTML = `<span>⚠️</span> <span>${errorMsg}</span>`;
      return false;
    } else {
      input.classList.remove('is-invalid');
      if (feedback) feedback.remove();
      return true;
    }
  }

  // Name check: min 2 characters
  const checkName = () => validateField(nameInput, val => val.length >= 2, 'Full Name is required (minimum 2 characters).');

  // Email check: standard regex
  const checkEmail = () => validateField(emailInput, val => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val), 'Please enter a valid email address.');

  // Phone check: 10-digit Indian mobile number with optional +91
  const checkPhone = () => validateField(phoneInput, val => {
    const digits = val.replace(/\D/g, '');
    if (digits.length === 12 && digits.startsWith('91')) {
      return /^[6-9]/.test(digits.slice(2));
    }
    return digits.length === 10 && /^[6-9]/.test(digits);
  }, 'Enter a valid 10-digit Indian mobile number (e.g. 9876543210 or +91 9876543210).');

  if (nameInput) nameInput.addEventListener('input', checkName);
  if (emailInput) emailInput.addEventListener('input', checkEmail);
  if (phoneInput) phoneInput.addEventListener('input', checkPhone);

  loginForm.addEventListener('submit', (e) => {
    const isNValid = checkName();
    const isEValid = checkEmail();
    const isPValid = checkPhone();

    if (!isNValid || !isEValid || !isPValid) {
      e.preventDefault();
      // Shake the card slightly
      const card = document.querySelector('.login-card');
      if (card) {
        card.style.animation = 'shake 0.4s ease';
        setTimeout(() => { card.style.animation = ''; }, 450);
      }
    }
  });
}

/**
 * 3. Count-up Animation for Metric Numbers
 */
function initCountUp() {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  const metricElements = document.querySelectorAll('.count-up');
  metricElements.forEach(el => {
    const target = parseFloat(el.getAttribute('data-target') || '0');
    if (isNaN(target) || target === 0) return;

    const duration = 1200; // 1.2s
    const startTime = performance.now();

    function updateCounter(currentTime) {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // Ease out cubic
      const easeOut = 1 - Math.pow(1 - progress, 3);
      const currentVal = target * easeOut;

      // Format as Indian Currency
      el.textContent = formatIndianRupee(currentVal);

      if (progress < 1) {
        requestAnimationFrame(updateCounter);
      } else {
        el.textContent = formatIndianRupee(target);
      }
    }

    requestAnimationFrame(updateCounter);
  });
}

function formatIndianRupee(amount) {
  const isNegative = amount < 0;
  const absVal = Math.abs(amount).toFixed(2);
  const [intPart, decPart] = absVal.split('.');

  let formattedInt = '';
  if (intPart.length <= 3) {
    formattedInt = intPart;
  } else {
    const last3 = intPart.slice(-3);
    const rest = intPart.slice(0, -3);
    const groups = [];
    let r = rest;
    while (r.length > 2) {
      groups.unshift(r.slice(-2));
      r = r.slice(0, -2);
    }
    if (r.length > 0) groups.unshift(r);
    formattedInt = groups.join(',') + ',' + last3;
  }

  const sign = isNegative ? '-' : '';
  return `${sign}₹${formattedInt}.${decPart}`;
}

/**
 * 4. Mobile Hamburger Menu Toggle
 */
function initMobileMenu() {
  const toggleBtn = document.getElementById('mobileMenuToggle');
  const navLinks = document.getElementById('navLinksMenu');

  if (toggleBtn && navLinks) {
    toggleBtn.addEventListener('click', () => {
      navLinks.classList.toggle('mobile-open');
    });

    // Close menu when clicking outside
    document.addEventListener('click', (e) => {
      if (!toggleBtn.contains(e.target) && !navLinks.contains(e.target)) {
        navLinks.classList.remove('mobile-open');
      }
    });
  }
}

/**
 * 5. Toast Auto-Dismiss
 */
function initToasts() {
  const toasts = document.querySelectorAll('.toast');
  toasts.forEach(toast => {
    // Close button
    const closeBtn = toast.querySelector('.toast-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', () => {
        dismissToast(toast);
      });
    }

    // Auto dismiss after 4 seconds
    setTimeout(() => {
      dismissToast(toast);
    }, 4000);
  });

  function dismissToast(t) {
    if (!t) return;
    t.style.transition = 'all 0.3s ease';
    t.style.opacity = '0';
    t.style.transform = 'translateX(100%)';
    setTimeout(() => {
      t.remove();
    }, 300);
  }
}

/**
 * 6. Accessible Delete Confirmation Modal
 */
function initDeleteModal() {
  const modal = document.getElementById('deleteConfirmModal');
  if (!modal) return;

  const descElement = document.getElementById('deleteItemDescription');
  const form = document.getElementById('deleteTransactionForm');
  const cancelBtn = document.getElementById('cancelDeleteBtn');

  // Trigger buttons
  document.querySelectorAll('.btn-delete-trigger').forEach(btn => {
    btn.addEventListener('click', () => {
      const txId = btn.getAttribute('data-id');
      const desc = btn.getAttribute('data-desc');
      if (descElement) descElement.textContent = desc || 'this transaction';
      if (form) form.action = `/transactions/delete/${txId}`;
      modal.classList.add('active');
    });
  });

  if (cancelBtn) {
    cancelBtn.addEventListener('click', () => {
      modal.classList.remove('active');
    });
  }

  modal.addEventListener('click', (e) => {
    if (e.target === modal) {
      modal.classList.remove('active');
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal.classList.contains('active')) {
      modal.classList.remove('active');
    }
  });
}

/**
 * 7. Transaction Form Dynamic Category & Needs/Wants Switcher
 */
function initTransactionForm() {
  const form = document.getElementById('transactionForm');
  if (!form) return;

  const typeRadios = form.querySelectorAll('input[name="transaction_type"]');
  const categorySelect = document.getElementById('categorySelect');
  const needWantContainer = document.getElementById('needWantContainer');

  const expenseCategories = [
    'Food', 'Transport', 'Shopping', 'Subscriptions',
    'Education', 'Entertainment', 'Health', 'Bills', 'Other'
  ];

  const incomeCategories = [
    'Allowance', 'Salary', 'Freelance', 'Scholarship', 'Gift', 'Other'
  ];

  function updateFormState(selectedType, currentSelectedCat = '') {
    if (!categorySelect) return;

    const list = selectedType === 'income' ? incomeCategories : expenseCategories;
    categorySelect.innerHTML = '<option value="" disabled>-- Select Category --</option>';

    list.forEach(cat => {
      const opt = document.createElement('option');
      opt.value = cat;
      opt.textContent = cat;
      if (cat === currentSelectedCat) {
        opt.selected = true;
      }
      categorySelect.appendChild(opt);
    });

    // If current selected wasn't set, select first
    if (!categorySelect.value && list.length > 0) {
      categorySelect.selectedIndex = 1;
    }

    // Toggle Needs vs Wants radio (only for expense)
    if (needWantContainer) {
      if (selectedType === 'income') {
        needWantContainer.style.display = 'none';
      } else {
        needWantContainer.style.display = 'block';
      }
    }
  }

  typeRadios.forEach(radio => {
    radio.addEventListener('change', () => {
      if (radio.checked) {
        updateFormState(radio.value);
      }
    });
  });

  // Initial setup based on checked radio or default
  const checkedRadio = form.querySelector('input[name="transaction_type"]:checked');
  const initialType = checkedRadio ? checkedRadio.value : 'expense';
  const initialCat = categorySelect ? categorySelect.getAttribute('data-selected') || '' : '';
  updateFormState(initialType, initialCat);
}
