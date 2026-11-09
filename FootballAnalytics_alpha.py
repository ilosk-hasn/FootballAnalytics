

import numpy as np

# جمع بيانات المباريات الثلاث الأخيرة
num_matches = 3
matches = []

for i in range(num_matches):
    print(f"\nالمباراة {i+1}:")
    home_goals = int(input("أدخل عدد أهداف الفريق المضيف: "))
    away_goals = int(input("أدخل عدد أهداف الفريق الضيف: "))
    first_half_home_goals = int(input("أدخل أهداف الفريق المضيف في الشوط الأول: "))
    first_half_away_goals = int(input("أدخل أهداف الفريق الضيف في الشوط الأول: "))
    
    matches.append({
        "home_goals": home_goals,
        "away_goals": away_goals,
        "first_half_home_goals": first_half_home_goals,
        "first_half_away_goals": first_half_away_goals
    })

# تحويل البيانات إلى مصفوفة NumPy
matches_np = np.array([[m['home_goals'], m['away_goals'], m['first_half_home_goals'], m['first_half_away_goals']] for m in matches])

# حساب المتوسطات
avg_home_goals = np.mean(matches_np[:, 0])
avg_away_goals = np.mean(matches_np[:, 1])
avg_first_half_home_goals = np.mean(matches_np[:, 2])
avg_first_half_away_goals = np.mean(matches_np[:, 3])

# التوقعات العامة (كما في الكود السابق)
predictions = []

total_avg_goals = avg_home_goals + avg_away_goals
if total_avg_goals > 2.5:
    predictions.append(("أكثر من 2.5 أهداف", (total_avg_goals / 3) * 100))
else:
    predictions.append(("أقل من 2.5 أهداف", ((3 - total_avg_goals) / 3) * 100))

first_half_avg_goals = avg_first_half_home_goals + avg_first_half_away_goals
if first_half_avg_goals > 0.5:
    predictions.append(("هدف في الشوط الأول", (first_half_avg_goals / 1.5) * 100))
else:
    predictions.append(("بدون أهداف في الشوط الأول", ((1 - first_half_avg_goals) / 1) * 100))

if avg_home_goals > avg_away_goals:
    predictions.append(("فوز الفريق المضيف", (avg_home_goals / total_avg_goals) * 100))
elif avg_away_goals > avg_home_goals:
    predictions.append(("فوز الفريق الضيف", (avg_away_goals / total_avg_goals) * 100))
else:
    predictions.append(("تعادل", 50))

# توقع 5 نتائج محتملة مع نسب تحققها
results = []

results.append(("فوز المضيف 1-0", (avg_home_goals / total_avg_goals) * 50))
results.append(("فوز المضيف 2-1", (avg_home_goals / total_avg_goals) * 30))
results.append(("فوز الضيف 0-1", (avg_away_goals / total_avg_goals) * 40))
results.append(("فوز الضيف 1-2", (avg_away_goals / total_avg_goals) * 25))
results.append(("تعادل 1-1", 30 if avg_home_goals == avg_away_goals else 20))
results.append(("تعادل 0-0", 20 if total_avg_goals < 1 else 10))

# ترتيب التوقعات حسب النسبة
predictions.sort(key=lambda x: x[1], reverse=True)
results.sort(key=lambda x: x[1], reverse=True)

# عرض جميع التوقعات العامة
print("\nالتوقعات العامة (مرتبة حسب القوة):")
for prediction in predictions:
    print(f"- {prediction[0]}: {prediction[1]:.2f}%")

# عرض أهم 5 نتائج محتملة
print("\nأهم 5 نتائج شوط 1 محتملة:")
for i in range(5):
    print(f"- {results[i][0]}: نسبة التحقق {results[i][1]:.2f}%")

# عرض التوقع الأفضل العام
best_prediction = predictions[0]
print("\nالتوقع الأفضل بناءً على التحليل:")
print(f"التوقع: {best_prediction[0]} - نسبة الاحتمال: {best_prediction[1]:.2f}%")