/**
 * background.js - Dynamic Popping & Moving Finance Background for SpendSmart
 * =========================================================================
 * Spawns floating finance icons (💰, 🪙, 💵, 💳, 🏦, 🛍️, 🍔, 🚌, 🎓, 📈, 🎯, 🐷, ⭐, ✨, 🎉),
 * drifts them with depth-of-field opacity, triggers periodic popping bursts with confetti,
 * supports mouse/touch interaction, and pauses when tab is hidden for 60fps performance.
 */

(function () {
  'use strict';

  // Check user preference for reduced motion
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Icon pool
  const ICONS = ['💰', '🪙', '💵', '💳', '🏦', '🛍️', '🍔', '🚌', '🎓', '📈', '🎯', '🐷', '⭐', '✨', '🎉'];
  const COLORS = ['#6C5CE7', '#FF6B9D', '#FFB347', '#00CEC9', '#2ED573', '#4DA3FF'];

  let canvasContainer = null;
  let iconsList = [];
  let isRunning = true;
  let lastTime = performance.now();
  let nextAutoPopTime = performance.now() + 2500;

  function initBackground() {
    canvasContainer = document.getElementById('spendsmart-bg-canvas');
    if (!canvasContainer) {
      canvasContainer = document.createElement('div');
      canvasContainer.id = 'spendsmart-bg-canvas';
      canvasContainer.className = 'bg-canvas-container';
      document.body.prepend(canvasContainer);
    }

    // Add 4 large blurred gradient blobs
    createGradientBlobs();

    // Determine icon count based on screen width
    const isMobile = window.innerWidth < 768;
    const count = isMobile ? 14 : 26;

    // Spawn floating icons
    for (let i = 0; i < count; i++) {
      createFloatingIcon(true);
    }

    // Interactive hover / tap bonus
    window.addEventListener('mousemove', handleMouseMove, { passive: true });
    window.addEventListener('touchstart', handleTouchStart, { passive: true });

    // Tab visibility handling (pause animation when tab is inactive)
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        isRunning = false;
      } else {
        isRunning = true;
        lastTime = performance.now();
        requestAnimationFrame(animateLoop);
      }
    });

    // Start 60fps animation loop if reduced motion is not requested
    if (!prefersReducedMotion) {
      requestAnimationFrame(animateLoop);
    }
  }

  function createGradientBlobs() {
    const blobs = [
      { color: 'rgba(108, 92, 231, 0.16)', top: '-5%', left: '-5%', width: '45vw', height: '45vw' },
      { color: 'rgba(255, 107, 157, 0.14)', top: '35%', right: '-5%', width: '40vw', height: '40vw' },
      { color: 'rgba(0, 206, 201, 0.12)', bottom: '-10%', left: '15%', width: '42vw', height: '42vw' },
      { color: 'rgba(255, 179, 71, 0.12)', top: '15%', left: '45%', width: '35vw', height: '35vw' }
    ];

    blobs.forEach((b, index) => {
      const blob = document.createElement('div');
      blob.className = `bg-gradient-blob blob-${index + 1}`;
      blob.style.background = b.color;
      if (b.top) blob.style.top = b.top;
      if (b.bottom) blob.style.bottom = b.bottom;
      if (b.left) blob.style.left = b.left;
      if (b.right) blob.style.right = b.right;
      blob.style.width = b.width;
      blob.style.height = b.height;
      canvasContainer.appendChild(blob);
    });
  }

  function createFloatingIcon(isInitial = false) {
    const el = document.createElement('span');
    el.className = 'floating-bg-icon';
    const char = ICONS[Math.floor(Math.random() * ICONS.length)];
    el.textContent = char;

    const size = Math.floor(Math.random() * 40) + 24; // 24px - 64px
    const opacity = (Math.random() * 0.25 + 0.25).toFixed(2); // 0.25 - 0.50
    const blur = (Math.random() * 1.5).toFixed(1); // 0 - 1.5px depth

    el.style.fontSize = `${size}px`;
    el.style.opacity = opacity;
    el.style.filter = `blur(${blur}px)`;

    const w = window.innerWidth;
    const h = window.innerHeight;

    const x = Math.random() * (w - size);
    const y = isInitial ? Math.random() * h : h + 20;

    const speedY = (Math.random() * 0.45 + 0.25); // slow upward drift
    const speedX = (Math.random() * 0.3 - 0.15); // gentle horizontal drift
    const wobbleSpeed = Math.random() * 0.002 + 0.001;
    const wobbleAmplitude = Math.random() * 20 + 10;
    const rotation = Math.random() * 360;
    const rotSpeed = (Math.random() * 0.4 - 0.2);

    const iconObj = {
      el,
      x,
      y,
      baseX: x,
      size,
      speedY,
      speedX,
      wobbleSpeed,
      wobbleAmplitude,
      wobblePhase: Math.random() * Math.PI * 2,
      rotation,
      rotSpeed,
      opacity,
      isPopping: false
    };

    updateIconTransform(iconObj);
    canvasContainer.appendChild(el);
    iconsList.push(iconObj);
    return iconObj;
  }

  function updateIconTransform(icon) {
    icon.el.style.transform = `translate3d(${icon.x.toFixed(1)}px, ${icon.y.toFixed(1)}px, 0) rotate(${icon.rotation.toFixed(1)}deg)`;
  }

  function popIcon(icon) {
    if (icon.isPopping) return;
    icon.isPopping = true;

    const rect = icon.el.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;

    // Burst sparkles / confetti
    spawnConfettiBurst(centerX, centerY);

    // Bounce and fade out
    icon.el.classList.add('pop-animation');

    setTimeout(() => {
      icon.el.classList.remove('pop-animation');
      icon.y = window.innerHeight + 30;
      icon.x = Math.random() * (window.innerWidth - icon.size);
      icon.baseX = icon.x;
      icon.isPopping = false;
      updateIconTransform(icon);
    }, 600);
  }

  function spawnConfettiBurst(x, y) {
    const particleCount = 8;
    for (let i = 0; i < particleCount; i++) {
      const p = document.createElement('div');
      p.className = 'burst-particle';
      const color = COLORS[Math.floor(Math.random() * COLORS.length)];
      p.style.backgroundColor = color;

      const angle = (Math.PI * 2 / particleCount) * i + (Math.random() * 0.4 - 0.2);
      const distance = Math.random() * 35 + 25;
      const dx = Math.cos(angle) * distance;
      const dy = Math.sin(angle) * distance;

      p.style.left = `${x}px`;
      p.style.top = `${y}px`;
      p.style.setProperty('--dx', `${dx}px`);
      p.style.setProperty('--dy', `${dy}px`);

      canvasContainer.appendChild(p);

      setTimeout(() => {
        p.remove();
      }, 700);
    }
  }

  function handleMouseMove(e) {
    if (prefersReducedMotion) return;
    const mx = e.clientX;
    const my = e.clientY;

    for (let i = 0; i < iconsList.length; i++) {
      const icon = iconsList[i];
      if (icon.isPopping) continue;

      const dist = Math.hypot(mx - (icon.x + icon.size / 2), my - (icon.y + icon.size / 2));
      if (dist < 60) {
        popIcon(icon);
        break; // pop one at a time for smooth elegance
      }
    }
  }

  function handleTouchStart(e) {
    if (prefersReducedMotion || !e.touches || !e.touches[0]) return;
    const touch = e.touches[0];
    const tx = touch.clientX;
    const ty = touch.clientY;

    for (let i = 0; i < iconsList.length; i++) {
      const icon = iconsList[i];
      if (icon.isPopping) continue;

      const dist = Math.hypot(tx - (icon.x + icon.size / 2), ty - (icon.y + icon.size / 2));
      if (dist < 70) {
        popIcon(icon);
        break;
      }
    }
  }

  function animateLoop(now) {
    if (!isRunning) return;

    const delta = Math.min((now - lastTime) / 16.66, 2.5); // Normalize to 60fps
    lastTime = now;

    // Periodic auto-pop of random icon
    if (now > nextAutoPopTime) {
      const unpopped = iconsList.filter(i => !i.isPopping && i.y > 100 && i.y < window.innerHeight - 100);
      if (unpopped.length > 0) {
        const randIcon = unpopped[Math.floor(Math.random() * unpopped.length)];
        popIcon(randIcon);
      }
      nextAutoPopTime = now + (Math.random() * 2500 + 2000);
    }

    const h = window.innerHeight;
    const w = window.innerWidth;

    for (let i = 0; i < iconsList.length; i++) {
      const icon = iconsList[i];
      if (icon.isPopping) continue;

      icon.y -= icon.speedY * delta;
      icon.wobblePhase += icon.wobbleSpeed * delta;
      icon.x = icon.baseX + Math.sin(icon.wobblePhase) * icon.wobbleAmplitude;
      icon.rotation += icon.rotSpeed * delta;

      // Wrap around screen top
      if (icon.y < -80) {
        icon.y = h + 20;
        icon.baseX = Math.random() * (w - icon.size);
        icon.x = icon.baseX;
      }

      updateIconTransform(icon);
    }

    requestAnimationFrame(animateLoop);
  }

  // Initialize on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initBackground);
  } else {
    initBackground();
  }
})();
