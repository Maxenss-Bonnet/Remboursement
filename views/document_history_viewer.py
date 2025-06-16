import os
import customtkinter as ctk


class DocumentHistoryViewer(ctk.CTkToplevel):
    def __init__(self, master, demande_data: dict, callbacks: dict):
        super().__init__(master)

        self.demande_data = demande_data
        self.callbacks = callbacks
        self.id_demande = self.demande_data.get("id_demande")

        self.title(f"Historique des Documents - Demande {self.id_demande[:8]}")
        self.geometry("700x500")
        self.transient(master)
        self.grab_set()
        self.resizable(True, True)

        main_frame = ctk.CTkScrollableFrame(self)
        main_frame.pack(expand=True, fill="both", padx=10, pady=10)

        label_font = ctk.CTkFont(weight="bold")

        chemins_factures_rel = self.demande_data.get("chemins_factures_stockees", [])
        if chemins_factures_rel:
            ctk.CTkLabel(main_frame, text="Historique des Factures:", font=label_font).pack(anchor="w", pady=(10, 5))
            for idx, rel_path in enumerate(chemins_factures_rel):
                item_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
                item_frame.pack(fill="x", pady=2)
                ctk.CTkLabel(item_frame, text=f"Version {idx + 1}: {os.path.basename(rel_path)}").pack(side="left", padx=5)
                ctk.CTkButton(item_frame, text="DL", width=60,
                              command=lambda d=self.id_demande, p=rel_path: self.callbacks['dl_pj'](d, p)).pack(side="right", padx=2)
                ctk.CTkButton(item_frame, text="Voir", width=60,
                              command=lambda d=self.id_demande, p=rel_path: self.callbacks['voir_pj'](d, p)).pack(side="right", padx=2)

        chemins_ribs_rel = self.demande_data.get("chemins_rib_stockes", [])
        if chemins_ribs_rel:
            ctk.CTkLabel(main_frame, text="Historique des RIBs:", font=label_font).pack(anchor="w", pady=(15, 5))
            for idx, rel_path in enumerate(chemins_ribs_rel):
                item_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
                item_frame.pack(fill="x", pady=2)
                ctk.CTkLabel(item_frame, text=f"Version {idx + 1}: {os.path.basename(rel_path)}").pack(side="left", padx=5)
                ctk.CTkButton(item_frame, text="DL", width=60,
                              command=lambda d=self.id_demande, p=rel_path: self.callbacks['dl_pj'](d, p)).pack(side="right", padx=2)
                ctk.CTkButton(item_frame, text="Voir", width=60,
                              command=lambda d=self.id_demande, p=rel_path: self.callbacks['voir_pj'](d, p)).pack(side="right", padx=2)

        chemins_trop_percu_rel = self.demande_data.get("chemins_trop_percu_stockes", [])
        if chemins_trop_percu_rel:
            ctk.CTkLabel(main_frame, text="Historique des Preuves de Trop-Perçu:", font=label_font).pack(anchor="w", pady=(15, 5))
            for idx, rel_path in enumerate(chemins_trop_percu_rel):
                item_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
                item_frame.pack(fill="x", pady=2)
                ctk.CTkLabel(item_frame, text=f"Version {idx + 1}: {os.path.basename(rel_path)}").pack(side="left", padx=5)
                ctk.CTkButton(item_frame, text="DL", width=60,
                              command=lambda d=self.id_demande, p=rel_path: self.callbacks['dl_pj'](d, p)).pack(side="right", padx=2)
                ctk.CTkButton(item_frame, text="Voir", width=60,
                              command=lambda d=self.id_demande, p=rel_path: self.callbacks['voir_pj'](d, p)).pack(side="right", padx=2)

        if not chemins_factures_rel and not chemins_ribs_rel and not chemins_trop_percu_rel:
            ctk.CTkLabel(main_frame, text="Aucun document historisé pour cette demande.").pack(pady=20)

        close_button = ctk.CTkButton(self, text="Fermer", command=self.destroy)
        close_button.pack(pady=10)