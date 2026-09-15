حزمة تجريبية لاختبار التقاط أسئلة مقابلة الذكاء الاصطناعي

المصدر:
Interview_Question_Bank(2).docx

المحتوى:
- 10 أسئلة عالية الأولوية من RAG وAgentic AI وLangGraph وGuardrails.
- 3 ملفات صوتية/متحدثين اصطناعيين مختلفين لكل سؤال.
- 6 ظروف صوتية لكل متحدث:
  1) clean
  2) fast
  3) office_noise
  4) far
  5) poor_call
  6) combined

الإجمالي:
180 ملف WAV، 16 kHz، mono.

مهم:
ملفات Indian/Jordanian/Kuwaiti في هذه الدفعة هي ملفات TTS اصطناعية محلية لاختبار المتانة،
وليست تسجيلات بشرية أصلية ولا لهجات وطنية موثقة. استخدمت تسميات synthetic بوضوح حتى
لا نخلط اختبار الضوضاء/البعد مع تقييم اللهجة البشرية الحقيقية.

الهدف:
اختبر كل ملف على النظام وسجل:
- transcript
- transcript confidence
- detected intent
- matched question id
- selected answer
- latency

النجاح الحقيقي:
قد يحتوي transcript على أخطاء، لكن يجب أن يصل النظام إلى intent والسؤال الصحيحين.
