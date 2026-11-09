import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import date
import threading
import customtkinter as ctk

from database.database import initialize
from database.repository import add_match, list_matches, delete_match, team_names, summary, save_prediction
from core.poisson import analyze
from core.ml_model import train_and_predict
from core.statistics import team_form
from services.import_export import export_file, import_file
from services.history_import import import_both

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class FootballAnalyticsApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        initialize()
        self.title("FootballAnalytics v2.0")
        self.geometry("1180x760")
        self.minsize(980, 650)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._sidebar()
        self.content = ctk.CTkFrame(self, corner_radius=0)
        self.content.grid(row=0, column=1, sticky="nsew", padx=16, pady=16)
        self.show_dashboard()

    def _sidebar(self):
        side = ctk.CTkFrame(self, width=210, corner_radius=0)
        side.grid(row=0, column=0, sticky="nsew")
        side.grid_propagate(False)
        ctk.CTkLabel(side, text="⚽ FootballAnalytics v2.0", font=ctk.CTkFont(size=20, weight="bold")).pack(padx=15,pady=(28,30))
        for label, callback in [
            ("لوحة التحكم", self.show_dashboard), ("إضافة مباراة", self.show_add),
            ("المباريات", self.show_matches), ("التحليل والتوقعات", self.show_analysis),
            ("استيراد / تصدير", self.show_import_export)]:
            ctk.CTkButton(side, text=label, command=callback, height=42, anchor="w").pack(fill="x", padx=14, pady=5)
        ctk.CTkLabel(side, text="SQLite • Poisson • ML-ready", text_color="gray").pack(side="bottom",pady=20)

    def _clear(self):
        for w in self.content.winfo_children(): w.destroy()

    def _heading(self, title, subtitle=""):
        ctk.CTkLabel(self.content, text=title, font=ctk.CTkFont(size=27, weight="bold")).pack(anchor="w", padx=22,pady=(20,3))
        if subtitle:
            ctk.CTkLabel(self.content, text=subtitle, text_color="gray").pack(anchor="w", padx=22,pady=(0,15))

    def show_dashboard(self):
        self._clear(); self._heading("لوحة التحكم", "ملخص قاعدة البيانات المحلية")
        s = summary()
        row = ctk.CTkFrame(self.content, fg_color="transparent"); row.pack(fill="x", padx=15,pady=12)
        for title, value in [("المباريات",s["matches"]),("الفرق",s["teams"]),("متوسط أهداف المباراة",s["avg_goals"])]:
            card=ctk.CTkFrame(row); card.pack(side="left",expand=True,fill="x",padx=7)
            ctk.CTkLabel(card,text=title,text_color="gray").pack(pady=(18,4))
            ctk.CTkLabel(card,text=str(value),font=ctk.CTkFont(size=30,weight="bold")).pack(pady=(0,18))
        ctk.CTkLabel(self.content,text="آخر المباريات",font=ctk.CTkFont(size=19,weight="bold")).pack(anchor="w",padx=22,pady=12)
        self._table(list_matches(8), self.content)

    def _table(self, rows, parent):
        cols=("date","home","score","away","ht","competition")
        frame=ttk.Frame(parent); frame.pack(fill="both",expand=True,padx=20,pady=8)
        tree=ttk.Treeview(frame,columns=cols,show="headings",height=12)
        heads={"date":"التاريخ","home":"المضيف","score":"النتيجة","away":"الضيف","ht":"الشوط الأول","competition":"البطولة"}
        widths={"date":100,"home":180,"score":80,"away":180,"ht":100,"competition":150}
        for c in cols: tree.heading(c,text=heads[c]); tree.column(c,width=widths[c],anchor="center")
        for m in rows:
            ht = "غير متاح" if m["ht_home_goals"] is None or m["ht_away_goals"] is None else f'{m["ht_home_goals"]}-{m["ht_away_goals"]}'
            tree.insert("", "end", values=(m["match_date"],m["home_team"],f'{m["home_goals"]}-{m["away_goals"]}',m["away_team"],ht,m["competition"]))
        tree.pack(side="left",fill="both",expand=True)
        scroll=ttk.Scrollbar(frame,orient="vertical",command=tree.yview); tree.configure(yscrollcommand=scroll.set); scroll.pack(side="right",fill="y")
        return tree

    def show_add(self):
        self._clear(); self._heading("إضافة مباراة", "أدخل النتيجة النهائية ونتيجة الشوط الأول")
        form=ctk.CTkFrame(self.content); form.pack(fill="x",padx=22,pady=12)
        fields={}
        specs=[("home_team","الفريق المضيف",""),("away_team","الفريق الضيف",""),("competition","البطولة (اختياري)",""),("match_date","التاريخ YYYY-MM-DD",date.today().isoformat()),("home_goals","أهداف المضيف","0"),("away_goals","أهداف الضيف","0"),("ht_home_goals","أهداف المضيف في الشوط الأول","0"),("ht_away_goals","أهداف الضيف في الشوط الأول","0")]
        for i,(key,label,default) in enumerate(specs):
            r,c=divmod(i,2)
            cell=ctk.CTkFrame(form,fg_color="transparent"); cell.grid(row=r,column=c,sticky="ew",padx=12,pady=9)
            ctk.CTkLabel(cell,text=label).pack(anchor="w")
            ent=ctk.CTkEntry(cell,height=36); ent.pack(fill="x",pady=4); ent.insert(0,default); fields[key]=ent
        form.grid_columnconfigure((0,1),weight=1)
        ctk.CTkLabel(form,text="ملاحظات (اختياري)").grid(row=4,column=0,sticky="w",padx=12)
        notes=ctk.CTkEntry(form); notes.grid(row=5,column=0,columnspan=2,sticky="ew",padx=12,pady=(3,15))
        def save():
            try:
                data={k:v.get().strip() for k,v in fields.items()}
                for k in ("home_goals","away_goals","ht_home_goals","ht_away_goals"): data[k]=int(data[k])
                data["notes"]=notes.get()
                add_match(data)
                messagebox.showinfo("تم","تم حفظ المباراة بنجاح.")
                self.show_dashboard()
            except Exception as e: messagebox.showerror("خطأ في البيانات",str(e))
        ctk.CTkButton(self.content,text="حفظ المباراة",command=save,height=42).pack(anchor="e",padx=22,pady=10)

    def show_matches(self):
        self._clear(); self._heading("سجل المباريات","اختَر مباراة ثم احذفها عند الحاجة")
        rows=list_matches()
        tree=self._table(rows,self.content)
        def remove():
            sel=tree.selection()
            if not sel: return messagebox.showwarning("تنبيه","اختَر مباراة أولاً")
            idx=tree.index(sel[0])
            if messagebox.askyesno("تأكيد","هل تريد حذف المباراة المحددة؟"):
                delete_match(rows[idx]["id"]); self.show_matches()
        ctk.CTkButton(self.content,text="حذف المباراة المحددة",fg_color="#9b3030",command=remove).pack(anchor="e",padx=22,pady=8)

    def show_analysis(self):
        self._clear(); self._heading("التحليل والتوقعات","Poisson إحصائي + طبقة ML اختيارية عند توفر البيانات")
        teams=team_names()
        if len(teams)<2:
            ctk.CTkLabel(self.content,text="أضف مباريات كافية وفريقين على الأقل لبدء التحليل.").pack(pady=30); return
        area=ctk.CTkFrame(self.content); area.pack(fill="x",padx=22,pady=12)
        home=ctk.StringVar(value=teams[0]); away=ctk.StringVar(value=teams[1])
        ctk.CTkLabel(area,text="المضيف").grid(row=0,column=0,padx=10,pady=10)
        ctk.CTkOptionMenu(area,values=teams,variable=home).grid(row=1,column=0,padx=10,pady=8)
        ctk.CTkLabel(area,text="الضيف").grid(row=0,column=1,padx=10,pady=10)
        ctk.CTkOptionMenu(area,values=teams,variable=away).grid(row=1,column=1,padx=10,pady=8)
        output=ctk.CTkTextbox(self.content,height=360); output.pack(fill="both",expand=True,padx=22,pady=12)
        def run():
            output.delete("1.0","end")
            try:
                if home.get()==away.get(): raise ValueError("اختَر فريقين مختلفين")
                matches=list_matches(10000)
                result=analyze(matches,home.get(),away.get())
                ml=train_and_predict(matches,home.get(),away.get())
                lines=[f'النموذج الأساسي: {result["model"]}',
                       f'معدل الأهداف المتوقع — {home.get()}: {result["lambda_home"]:.2f}',
                       f'معدل الأهداف المتوقع — {away.get()}: {result["lambda_away"]:.2f}',"",
                       "احتمالات 1X2:",
                       f'فوز {home.get()}: {result["home_win"]:.1%}',
                       f'تعادل: {result["draw"]:.1%}',
                       f'فوز {away.get()}: {result["away_win"]:.1%}',"",
                       f'Over 2.5: {result["over_25"]:.1%}',
                       f'Under 2.5: {result["under_25"]:.1%}',
                       f'الفريقان يسجلان BTTS: {result["btts"]:.1%}',"",
                       "أكثر النتائج الدقيقة احتمالاً:"]
                lines += [f"{h}-{a} : {p:.1%}" for h,a,p in result["scores"]]
                lines += ["","طبقة Machine Learning:"]
                if ml["available"]:
                    p=ml["probabilities"]
                    lines += [f'فوز المضيف: {p["home_win"]:.1%}',f'تعادل: {p["draw"]:.1%}',f'فوز الضيف: {p["away_win"]:.1%}',ml["warning"]]
                else: lines.append(ml["reason"])
                lines += ["","تنبيه: هذه تقديرات مبنية على البيانات المسجلة وليست ضماناً للنتيجة."]
                output.insert("end","\n".join(lines))
                save_prediction(home.get(),away.get(),result)
            except Exception as e: output.insert("end","تعذر التحليل: "+str(e))
        ctk.CTkButton(area,text="تحليل المباراة",command=run).grid(row=1,column=2,padx=20,pady=8)

    def show_import_export(self):
        self._clear(); self._heading("استيراد وتصدير","يدعم CSV وExcel بصيغة الأعمدة الموضحة في القالب")
        panel = ctk.CTkFrame(self.content)
        panel.pack(fill="x", padx=22, pady=(4, 12))
        body = ctk.CTkFrame(panel, fg_color="transparent")
        state = {"open": False}
        def toggle():
            if state["open"]:
                body.pack_forget(); toggle_btn.configure(text="＋ استيراد سجل الفريقين السابق")
            else:
                body.pack(fill="x", padx=12, pady=(0, 12)); toggle_btn.configure(text="－ إخفاء استيراد سجل الفريقين")
            state["open"] = not state["open"]
        toggle_btn = ctk.CTkButton(panel, text="＋ استيراد سجل الفريقين السابق", command=toggle, anchor="w")
        toggle_btn.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(body, text="المصدر: ESPN • الطريقة: both • العدد: 20 مباراة سابقة لكل فريق. أدخل رمز المسابقة مثل eng.1 واسمَي الفريقين كما يظهران لدى المصدر.", wraplength=840, justify="left").pack(anchor="w", pady=(0, 8))
        row = ctk.CTkFrame(body, fg_color="transparent"); row.pack(fill="x")
        inputs = {}
        for key, label, default in (("league", "رمز المسابقة", "eng.1"), ("home", "الفريق الأول", ""), ("away", "الفريق الثاني", "")):
            cell = ctk.CTkFrame(row, fg_color="transparent"); cell.pack(side="left", expand=True, fill="x", padx=5)
            ctk.CTkLabel(cell, text=label).pack(anchor="w")
            entry = ctk.CTkEntry(cell); entry.pack(fill="x", pady=(3, 8))
            if default: entry.insert(0, default)
            inputs[key] = entry
        status = ctk.CTkLabel(body, text="", text_color="gray", wraplength=840, justify="left")
        status.pack(anchor="w", pady=5)
        def start_history_import():
            values = {k: v.get().strip() for k, v in inputs.items()}
            if not values["home"] or not values["away"]:
                messagebox.showwarning("بيانات ناقصة", "أدخل اسمَي الفريقين أولاً."); return
            import_btn.configure(state="disabled", text="جارٍ جلب المباريات…")
            status.configure(text="يجري البحث في سجل الفريقين وجلب تفاصيل المباريات المتاحة؛ قد يستغرق ذلك بضع دقائق.")
            def work():
                try: result = import_both(values["league"], values["home"], values["away"], count=20)
                except Exception as exc: result = {"fatal": str(exc)}
                self.after(0, lambda: finish_history_import(result))
            threading.Thread(target=work, daemon=True).start()
        def finish_history_import(result):
            import_btn.configure(state="normal", text="استيراد 20 مباراة لكل فريق")
            if result.get("fatal"):
                status.configure(text="فشل الاستيراد: " + result["fatal"], text_color="#ff8080"); return
            lines = [f"اكتُشفت {result['found']} مباراة فريدة؛ أُضيفت {result['added']}؛ تم تجاوز {result['skipped']} موجودة بالفعل."]
            lines.extend(result.get("errors", []))
            lines.append("الحقائق المتاحة وتوثيق المصدر محفوظة في ملاحظات كل مباراة. القيم غير المتاحة تبقى فارغة.")
            status.configure(text="\n".join(lines), text_color="gray")
        import_btn = ctk.CTkButton(body, text="استيراد 20 مباراة لكل فريق", command=start_history_import, height=40)
        import_btn.pack(anchor="w", pady=(5, 2))
        ctk.CTkLabel(body, text="الاستيراد يتطلب اتصالاً بالإنترنت وتختلف تغطية الإحصائيات والتشكيلات والغيابات حسب المسابقة والمباراة.", text_color="gray", wraplength=840, justify="left").pack(anchor="w", pady=(6, 0))
        toggle()
        ctk.CTkLabel(self.content,text="الأعمدة المطلوبة: match_date, competition, home_team, away_team, home_goals, away_goals, ht_home_goals, ht_away_goals, notes",wraplength=850).pack(anchor="w",padx=22,pady=18)
        def do_import():
            path=filedialog.askopenfilename(filetypes=[("CSV / Excel","*.csv *.xlsx *.xls")])
            if not path:return
            try:
                count,errors=import_file(path)
                msg=f"تم استيراد {count} مباراة."
                if errors: msg+="\n\nأخطاء:\n"+"\n".join(errors[:12])
                messagebox.showinfo("نتيجة الاستيراد",msg); self.show_dashboard()
            except Exception as e: messagebox.showerror("خطأ",str(e))
        def do_export():
            path=filedialog.asksaveasfilename(defaultextension=".xlsx",filetypes=[("Excel","*.xlsx"),("CSV","*.csv")])
            if not path:return
            try: export_file(path,list_matches(100000)); messagebox.showinfo("تم","تم تصدير البيانات.")
            except Exception as e: messagebox.showerror("خطأ",str(e))
        ctk.CTkButton(self.content,text="استيراد CSV / Excel",command=do_import,height=45).pack(anchor="w",padx=22,pady=12)
        ctk.CTkButton(self.content,text="تصدير CSV / Excel",command=do_export,height=45).pack(anchor="w",padx=22,pady=12)
        ctk.CTkLabel(self.content,text="نصيحة: صدّر نسخة احتياطية قبل استيراد دفعة كبيرة.",text_color="gray").pack(anchor="w",padx=22,pady=15)
