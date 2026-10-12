/**
 * Psmhealthcare Application - Client Script
 * Flash alerts, mobile nav, booking wizard, payment checkout
 */

document.addEventListener("DOMContentLoaded", function () {

    // ====================================================
    // FLASH MESSAGE DISMISSAL
    // ====================================================
    document.querySelectorAll(".flash").forEach(flash => {
        const dismiss = () => {
            flash.style.opacity = "0";
            flash.style.transform = "translateX(30px)";
            setTimeout(() => flash.remove(), 260);
        };
        flash.addEventListener("click", dismiss);
        setTimeout(dismiss, 6000);
    });

    // ====================================================
    // THEME TOGGLE (dark / light)
    // ====================================================
    const themeToggle = document.getElementById("themeToggle");
    if (themeToggle) {
        themeToggle.addEventListener("click", () => {
            const current = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
            document.documentElement.setAttribute("data-theme", current);
            localStorage.setItem("Psmhealthcarehealthcare-theme", current);
        });
    }

    // ====================================================
    // 3D TILT EFFECT
    // ====================================================
    function initTilt() {
        const cards = document.querySelectorAll("[data-tilt]");
        if (!cards.length || window.matchMedia("(hover: none)").matches) return;
        const max = 10;

        cards.forEach(card => {
            card.addEventListener("mouseenter", () => {
                card.style.transition = "transform 0.12s ease-out, box-shadow 0.3s ease";
            });
            card.addEventListener("mousemove", (e) => {
                const rect = card.getBoundingClientRect();
                const px = (e.clientX - rect.left) / rect.width;
                const py = (e.clientY - rect.top) / rect.height;
                const rx = (0.5 - py) * max;
                const ry = (px - 0.5) * max;
                card.style.transform =
                    `rotateX(${rx.toFixed(2)}deg) rotateY(${ry.toFixed(2)}deg) translateY(-6px) scale(1.015)`;
            });
            card.addEventListener("mouseleave", () => {
                card.style.transition = "transform 0.4s ease, box-shadow 0.4s ease";
                card.style.transform = "";
            });
        });
    }
    initTilt();

    // ====================================================
    // MOBILE NAVIGATION
    // ====================================================
    const navToggle = document.getElementById("navToggle");
    const navLinks = document.getElementById("navLinks");
    if (navToggle && navLinks) {
        navToggle.addEventListener("click", () => {
            const open = navLinks.classList.toggle("is-open");
            navToggle.setAttribute("aria-expanded", String(open));
        });
        navLinks.querySelectorAll("a").forEach(link => {
            link.addEventListener("click", () => navLinks.classList.remove("is-open"));
        });
    }

    // ====================================================
    // SIGNUP VALIDATION
    // ====================================================
    const signupForm = document.getElementById("signup-form");
    if (signupForm) {
        const pass = document.getElementById("password");
        const confirmPass = document.getElementById("confirm_password");
        signupForm.addEventListener("submit", (e) => {
            if (pass && confirmPass && pass.value !== confirmPass.value) {
                e.preventDefault();
                confirmPass.setCustomValidity("Passwords do not match.");
                confirmPass.reportValidity();
                confirmPass.setCustomValidity("");
                confirmPass.focus();
            }
        });
    }

    // ====================================================
    // BOOKING WIZARD
    // ====================================================
    const branch = document.getElementById("branch");
    const doctor = document.getElementById("doctor");
    const appointmentDate = document.getElementById("appointmentDate");
    const slots = document.getElementById("slots");
    const appointmentTime = document.getElementById("appointmentTime");
    const bookButton = document.getElementById("bookButton");
    const bookLaterButton = document.getElementById("bookLaterButton");
    const slotStatus = document.getElementById("slotStatus");
    const bookingForm = document.getElementById("bookingForm");

    if (branch && doctor && bookingForm) {
        const panels = Array.from(document.querySelectorAll(".step-panel"));
        const stepNodes = Array.from(document.querySelectorAll("#stepper .step"));
        const timePreview = document.getElementById("selectedTimePreview");
        let currentStep = 1;
        let availabilityRequest = 0;
        const setBookingButtonsDisabled = disabled => {
            if (bookButton) bookButton.disabled = disabled;
            if (bookLaterButton) bookLaterButton.disabled = disabled;
        };

        const setText = (id, value) => {
            const node = document.getElementById(id);
            if (node) node.textContent = value;
        };

        const formatDate = (isoDate) => {
            if (!isoDate) return "Not selected";
            const [y, m, d] = isoDate.split("-").map(Number);
            return new Date(y, m - 1, d).toLocaleDateString("en-GB", {
                weekday: "short", day: "numeric", month: "short", year: "numeric"
            });
        };

        const formatTime = (isoDateTime) => {
            if (!isoDateTime) return "Not selected";
            const time = isoDateTime.slice(11, 16);
            const [h, m] = time.split(":").map(Number);
            const suffix = h >= 12 ? "PM" : "AM";
            const hour12 = ((h + 11) % 12) + 1;
            return `${hour12}:${String(m).padStart(2, "0")} ${suffix}`;
        };

        function syncSummary() {
            const branchLabel = branch.selectedOptions[0] ? branch.selectedOptions[0].text : "";
            const doctorLabel = doctor.selectedOptions[0] ? doctor.selectedOptions[0].text : "";
            const dateValue = appointmentDate ? appointmentDate.value : "";
            const timeValue = appointmentTime ? appointmentTime.value : "";

            setText("sumBranch", branch.value ? branchLabel : "Not selected");
            setText("sumDoctor", doctor.value ? doctorLabel : "Not selected");
            setText("sumDate", formatDate(dateValue));
            setText("sumTime", formatTime(timeValue));

            setText("reviewBranch", branch.value ? branchLabel : "-");
            setText("reviewDoctor", doctor.value ? doctorLabel : "-");
            setText("reviewDate", dateValue ? formatDate(dateValue) : "-");
            setText("reviewTime", timeValue ? formatTime(timeValue) : "-");

            const timeNode = document.getElementById("sumTime");
            if (timeNode) timeNode.classList.toggle("pending-value", !timeValue);
        }

        function goToStep(step) {
            currentStep = step;
            panels.forEach(panel => {
                panel.classList.toggle("is-active", Number(panel.dataset.panel) === step);
            });
            stepNodes.forEach(node => {
                const n = Number(node.dataset.step);
                node.classList.toggle("is-active", n === step);
                node.classList.toggle("is-done", n < step);
                if (n === step) node.setAttribute("aria-current", "step");
                else node.removeAttribute("aria-current");
                const num = node.querySelector(".num");
                if (num) num.textContent = n < step ? "✓" : String(n);
            });
            const layout = document.querySelector(".stepper");
            if (layout) {
                const top = layout.getBoundingClientRect().top + window.scrollY - 100;
                window.scrollTo({ top, behavior: "smooth" });
            }
        }

        function step1Ready() {
            return Boolean(branch.value && doctor.value);
        }

        function step2Ready() {
            return Boolean(appointmentDate && appointmentDate.value && appointmentTime.value);
        }

        document.querySelectorAll("[data-next]").forEach(btn => {
            btn.addEventListener("click", () => {
                const target = Number(btn.dataset.next);
                if (target === 2 && !step1Ready()) return;
                if (target === 3 && !step2Ready()) return;
                goToStep(target);
            });
        });

        document.querySelectorAll("[data-back]").forEach(btn => {
            btn.addEventListener("click", () => goToStep(Number(btn.dataset.back)));
        });

        // --- Doctors by department ---
        branch.addEventListener("change", async function () {
            doctor.innerHTML = '<option value="">Loading doctors...</option>';
            doctor.disabled = true;
            if (appointmentTime) appointmentTime.value = "";
            if (timePreview) timePreview.value = "";
            setBookingButtonsDisabled(true);
            const step3Btn = document.getElementById("toStep3");
            if (step3Btn) step3Btn.disabled = true;
            slotPlaceholder("Select a doctor and date to see available times.", false);
            if (slotStatus) slotStatus.textContent = "Select a doctor and date";
            const step2Btn = document.getElementById("toStep2");
            if (step2Btn) step2Btn.disabled = true;

            if (!branch.value) {
                doctor.innerHTML = '<option value="">Select department first</option>';
                syncSummary();
                return;
            }

            try {
                const response = await fetch(`/api/doctors?branch_id=${encodeURIComponent(branch.value)}`);
                const list = await response.json();
                doctor.innerHTML = '<option value="">Select doctor</option>';
                list.forEach(item => {
                    const option = document.createElement("option");
                    option.value = item.id;
                    option.textContent = `Dr. ${item.name}`;
                    doctor.appendChild(option);
                });
                doctor.disabled = list.length === 0;
                if (list.length === 0) {
                    doctor.innerHTML = '<option value="">No doctors in this department</option>';
                }
            } catch (error) {
                console.error("Failed to load doctors:", error);
                doctor.innerHTML = '<option value="">Error loading doctors</option>';
            }
            syncSummary();
        });

        doctor.addEventListener("change", function () {
            const step2Btn = document.getElementById("toStep2");
            if (step2Btn) step2Btn.disabled = !step1Ready();
            if (appointmentTime) appointmentTime.value = "";
            if (timePreview) timePreview.value = "";
            setBookingButtonsDisabled(true);
            const step3Btn = document.getElementById("toStep3");
            if (step3Btn) step3Btn.disabled = true;
            syncSummary();
            loadAvailability();
        });

        if (appointmentDate) {
            appointmentDate.addEventListener("change", function () {
                if (appointmentTime) appointmentTime.value = "";
                if (timePreview) timePreview.value = "";
                setBookingButtonsDisabled(true);
                const step3Btn = document.getElementById("toStep3");
                if (step3Btn) step3Btn.disabled = true;
                syncSummary();
                loadAvailability();
            });
        }

        // --- Availability ---
        function slotPlaceholder(message, isError) {
            if (!slots) return;
            slots.classList.remove("grouped");
            slots.innerHTML = "";
            const box = document.createElement("div");
            box.className = "slot-placeholder" + (isError ? " error-state" : "");
            box.textContent = message;
            slots.appendChild(box);
        }

        function renderGroup(label, slotList, icon) {
            const heading = document.createElement("div");
            heading.className = "slot-group-label";
            heading.innerHTML = icon + "<span>" + label + "</span>";
            slots.appendChild(heading);

            const grid = document.createElement("div");
            grid.className = "slot-grid";
            slotList.forEach(slot => {
                const button = document.createElement("button");
                button.type = "button";
                button.className = "slot";
                button.textContent = slot.label;
                button.dataset.value = slot.value;
                if (appointmentTime.value === slot.value) {
                    button.classList.add("selected");
                }
                button.addEventListener("click", () => {
                    slots.querySelectorAll(".slot").forEach(btn => btn.classList.remove("selected"));
                    button.classList.add("selected");
                    appointmentTime.value = slot.value;
                    if (timePreview) timePreview.value = slot.label;
                    setBookingButtonsDisabled(false);
                    const step3Btn = document.getElementById("toStep3");
                    if (step3Btn) step3Btn.disabled = false;
                    syncSummary();
                });
                grid.appendChild(button);
            });
            slots.appendChild(grid);
        }

        async function loadAvailability(silent = false) {
            const doctorId = doctor.value;
            const selectedDate = appointmentDate ? appointmentDate.value : "";

            if (!doctorId || !selectedDate) {
                availabilityRequest += 1;
                slotPlaceholder("Select a doctor and date to see available times.", false);
                if (slotStatus) slotStatus.textContent = "Select a doctor and date";
                return;
            }

            const [y, m, d] = selectedDate.split("-").map(Number);
            if (new Date(y, m - 1, d).getDay() === 0) {
                slotPlaceholder("The clinic is closed on Sundays. Open Mon - Sat, 9:00 AM to 5:00 PM.", true);
                if (slotStatus) slotStatus.textContent = "Closed on Sundays";
                return;
            }

            if (!silent) {
                if (slotStatus) slotStatus.textContent = "Checking live availability...";
                slotPlaceholder("Checking available 30-minute consultation slots...", false);
            }
            const requestId = ++availabilityRequest;

            try {
                const response = await fetch(
                    `/api/availability?doctor_id=${encodeURIComponent(doctorId)}&date=${encodeURIComponent(selectedDate)}`,
                    { cache: "no-store" }
                );
                const data = await response.json();
                if (!response.ok) throw new Error(data.error || "Server error fetching availability.");
                if (requestId !== availabilityRequest) return;

                if (!data.slots || data.slots.length === 0) {
                    const selectionWasLost = Boolean(appointmentTime.value);
                    appointmentTime.value = "";
                    if (timePreview) timePreview.value = "";
                    setBookingButtonsDisabled(true);
                    const step3Btn = document.getElementById("toStep3");
                    if (step3Btn) step3Btn.disabled = true;
                    slotPlaceholder("No open slots on this date. Try another day.", false);
                    if (slotStatus) {
                        slotStatus.textContent = selectionWasLost
                            ? "Your selected time was just booked. No availability remains."
                            : "No availability";
                    }
                    if (selectionWasLost && currentStep > 2) goToStep(2);
                    syncSummary();
                    return;
                }

                const selectedStillAvailable = data.slots.some(slot => slot.value === appointmentTime.value);
                const selectionWasLost = Boolean(appointmentTime.value) && !selectedStillAvailable;
                if (selectionWasLost) {
                    appointmentTime.value = "";
                    if (timePreview) timePreview.value = "";
                    syncSummary();
                    if (currentStep > 2) goToStep(2);
                }

                if (slotStatus) {
                    slotStatus.textContent = selectionWasLost
                        ? "Your selected time was just booked. Choose another available time."
                        : `${data.slots.length} slot${data.slots.length > 1 ? "s" : ""} available`;
                }
                setBookingButtonsDisabled(!appointmentTime.value);
                const step3Btn = document.getElementById("toStep3");
                if (step3Btn) step3Btn.disabled = !appointmentTime.value;

                const morning = data.slots.filter(s => s.value.slice(11, 16) < "12:00");
                const afternoon = data.slots.filter(s => s.value.slice(11, 16) >= "12:00");

                slots.innerHTML = "";
                slots.classList.add("grouped");
                if (morning.length) {
                    renderGroup("Morning · 9:00 AM - 12:00 PM", morning,
                        '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4"></circle><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"></path></svg>');
                }
                if (afternoon.length) {
                    renderGroup("Afternoon · 12:00 PM - 5:00 PM", afternoon,
                        '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M17 18a5 5 0 0 0-10 0"></path><line x1="12" y1="2" x2="12" y2="9"></line><line x1="4.2" y1="10.2" x2="5.6" y2="11.6"></line><line x1="1" y1="18" x2="3" y2="18"></line><line x1="21" y1="18" x2="23" y2="18"></line><line x1="18.4" y1="11.6" x2="19.8" y2="10.2"></line><line x1="23" y1="22" x2="1" y2="22"></line></svg>');
                }
            } catch (error) {
                if (requestId !== availabilityRequest) return;
                console.error("Availability error:", error);
                slotPlaceholder("Unable to check availability right now. Please try again.", true);
                if (slotStatus) slotStatus.textContent = "Error checking availability";
                setBookingButtonsDisabled(true);
                const step3Btn = document.getElementById("toStep3");
                if (step3Btn) step3Btn.disabled = true;
                if (currentStep > 2) goToStep(2);
            }
        }

        window.setInterval(() => {
            if (!document.hidden && doctor.value && appointmentDate && appointmentDate.value) {
                loadAvailability(true);
            }
        }, 10000);
        window.addEventListener("focus", () => loadAvailability(true));
        document.addEventListener("visibilitychange", () => {
            if (!document.hidden) loadAvailability(true);
        });

        bookingForm.addEventListener("submit", (e) => {
            if (!step1Ready() || !step2Ready()) {
                e.preventDefault();
                goToStep(step1Ready() ? 2 : 1);
                return;
            }
            const paymentChoice = document.getElementById("paymentChoice");
            if (paymentChoice && e.submitter && e.submitter.dataset.paymentChoice) {
                paymentChoice.value = e.submitter.dataset.paymentChoice;
            }
            if (bookButton) {
                bookButton.disabled = true;
                bookButton.textContent = paymentChoice && paymentChoice.value === "pay_later"
                    ? "Confirming appointment..."
                    : "Reserving your slot...";
            }
            if (bookLaterButton) bookLaterButton.disabled = true;
        });

        syncSummary();
    }

    // ====================================================
    // PAYMENT CHECKOUT
    // ====================================================
    const paymentForm = document.getElementById("paymentForm");
    if (paymentForm) {
        const methodInputs = document.querySelectorAll('input[name="method"]');
        const panels = document.querySelectorAll("[data-method-panel]");
        const overlay = document.getElementById("payOverlay");
        const payError = document.getElementById("payError");
        const payBtn = document.getElementById("payBtn");

        const cardNumber = document.getElementById("card_number");
        const cardName = document.getElementById("card_name");
        const cardExpiry = document.getElementById("card_expiry");
        const cardCvv = document.getElementById("card_cvv");
        const upiId = document.getElementById("upi_id");
        const bank = document.getElementById("bank");

        const cvNumber = document.getElementById("cvNumber");
        const cvHolder = document.getElementById("cvHolder");
        const cvExpiry = document.getElementById("cvExpiry");
        const cardBrandLabel = document.getElementById("cardBrandLabel");

        function selectedMethod() {
            const checked = document.querySelector('input[name="method"]:checked');
            return checked ? checked.value : "card";
        }

        methodInputs.forEach(input => {
            input.addEventListener("change", () => {
                panels.forEach(panel => {
                    panel.classList.toggle("is-active", panel.dataset.methodPanel === selectedMethod());
                });
                if (payError) payError.hidden = true;
            });
        });

        function brandOf(number) {
            if (number.startsWith("4")) return "Visa";
            if (/^(5[1-5])/.test(number)) return "Mastercard";
            if (/^(34|37)/.test(number)) return "American Express";
            if (number.startsWith("6")) return "RuPay";
            return "Bank card";
        }

        if (cardNumber) {
            cardNumber.addEventListener("input", () => {
                const digits = cardNumber.value.replace(/\D/g, "").slice(0, 19);
                cardNumber.value = digits.replace(/(.{4})/g, "$1 ").trim();
                if (cvNumber) {
                    cvNumber.textContent = cardNumber.value || "•••• •••• •••• ••••";
                }
                if (cardBrandLabel) {
                    cardBrandLabel.textContent = digits.length >= 2 ? brandOf(digits) : "Your bank card";
                }
            });
        }

        if (cardName) {
            cardName.addEventListener("input", () => {
                if (cvHolder) cvHolder.textContent = cardName.value.toUpperCase() || "YOUR NAME";
            });
        }

        if (cardExpiry) {
            cardExpiry.addEventListener("input", () => {
                let digits = cardExpiry.value.replace(/\D/g, "").slice(0, 4);
                if (digits.length >= 3) {
                    digits = digits.slice(0, 2) + "/" + digits.slice(2);
                }
                cardExpiry.value = digits;
                if (cvExpiry) cvExpiry.textContent = digits || "MM/YY";
            });
        }

        if (cardCvv) {
            cardCvv.addEventListener("input", () => {
                cardCvv.value = cardCvv.value.replace(/\D/g, "").slice(0, 4);
            });
        }

        function showError(message) {
            if (!payError) return;
            payError.textContent = message;
            payError.hidden = false;
            payError.scrollIntoView({ behavior: "smooth", block: "center" });
        }

        function validate() {
            const method = selectedMethod();
            if (method === "card") {
                const number = cardNumber.value.replace(/\D/g, "");
                if (cardName.value.trim().length < 3) return "Please enter the name printed on your card.";
                if (number.length < 13) return "Please enter a valid card number.";
                if (!/^\d{2}\/\d{2}$/.test(cardExpiry.value)) return "Please enter the expiry as MM/YY.";
                const [mm, yy] = cardExpiry.value.split("/").map(Number);
                const now = new Date();
                const expDate = new Date(2000 + yy, mm, 0);
                if (mm < 1 || mm > 12 || expDate < now) return "That expiry date is invalid or has passed.";
                if (cardCvv.value.length < 3) return "Please enter the 3 digit security code.";
            } else if (method === "upi") {
                const value = upiId ? upiId.value.trim() : "";
                if (!value.includes("@") || value.length < 5) return "Please enter a valid UPI ID (e.g. name@upi).";
            } else if (method === "netbanking") {
                if (!bank || !bank.value) return "Please choose your bank.";
            }
            return null;
        }

        paymentForm.addEventListener("submit", (e) => {
            const error = validate();
            if (error) {
                e.preventDefault();
                showError(error);
                return;
            }
            if (payError) payError.hidden = true;

            e.preventDefault();
            if (overlay) overlay.classList.add("is-visible");
            if (payBtn) {
                payBtn.disabled = true;
                payBtn.textContent = "Processing...";
            }

            const steps = document.querySelectorAll("#processingSteps div");
            steps.forEach((step, index) => {
                setTimeout(() => step.classList.add("done"), 450 * (index + 1));
            });

            setTimeout(() => paymentForm.submit(), 450 * (steps.length + 1));
        });
    }
});
