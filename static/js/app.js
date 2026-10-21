/* Controle DET: máscaras de campos, confirmação de ações e avisos (toasts). */
(function () {
  "use strict";

  // ---------- Máscaras (o servidor valida de novo; isto é só conforto de digitação) ----------
  function soDigitos(v) { return v.replace(/\D/g, ""); }

  var MASCARAS = {
    cnpj: function (v) {
      var d = soDigitos(v).slice(0, 14), s = d;
      if (d.length > 12) s = d.slice(0, 2) + "." + d.slice(2, 5) + "." + d.slice(5, 8) + "/" + d.slice(8, 12) + "-" + d.slice(12);
      else if (d.length > 8) s = d.slice(0, 2) + "." + d.slice(2, 5) + "." + d.slice(5, 8) + "/" + d.slice(8);
      else if (d.length > 5) s = d.slice(0, 2) + "." + d.slice(2, 5) + "." + d.slice(5);
      else if (d.length > 2) s = d.slice(0, 2) + "." + d.slice(2);
      return s;
    },
    digitos: function (v) { return soDigitos(v); },
    codigo: function (v) { return v.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 20); },
  };

  document.querySelectorAll("[data-mask]").forEach(function (campo) {
    var f = MASCARAS[campo.dataset.mask];
    if (!f) return;
    campo.addEventListener("input", function () { campo.value = f(campo.value); });
    if (campo.value) campo.value = f(campo.value);
  });

  // ---------- Confirmação antes de enviar formulários marcados com data-confirmar ----------
  var modalEl = document.getElementById("modal-confirmar");
  var formPendente = null;

  document.addEventListener("submit", function (e) {
    var form = e.target;
    var mensagem = form.dataset && form.dataset.confirmar;
    if (!mensagem || form.dataset.confirmado === "1") return;
    e.preventDefault();
    if (!window.bootstrap || !modalEl) {          // sem o JS do Bootstrap, usa a confirmação do navegador
      if (window.confirm(mensagem)) { form.dataset.confirmado = "1"; form.submit(); }
      return;
    }
    formPendente = form;
    document.getElementById("modal-confirmar-texto").textContent = mensagem;
    window.bootstrap.Modal.getOrCreateInstance(modalEl).show();
  });

  if (modalEl) {
    document.getElementById("modal-confirmar-ok").addEventListener("click", function () {
      if (formPendente) { formPendente.dataset.confirmado = "1"; formPendente.submit(); }
    });
    modalEl.addEventListener("hidden.bs.modal", function () { formPendente = null; });
  }

  // ---------- Toasts: sucesso e informação somem sozinhos; erro e alerta ficam até fechar ----------
  if (window.bootstrap) {
    document.querySelectorAll(".toast").forEach(function (el) {
      var auto = el.dataset.autohide === "true";
      window.bootstrap.Toast.getOrCreateInstance(el, { autohide: auto, delay: 6000 }).show();
    });
  }
})();
