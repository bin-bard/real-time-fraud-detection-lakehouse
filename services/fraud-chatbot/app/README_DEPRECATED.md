# ⚠️ DEPRECATED CODE

## File: `chatbot.py.deprecated`

**Status:** OLD/OBSOLETE - DO NOT USE

### Lý do deprecated:

File `chatbot.py` này là phiên bản **monolithic cũ** của chatbot, được thay thế hoàn toàn bởi **modular architecture** mới.

### Architecture cũ (DEPRECATED):

- File duy nhất 1251 lines
- Logic phức tạp, khó maintain
- Không sử dụng LangChain ReAct Agent
- Keyword-based query parsing

### Architecture mới (HIỆN TẠI):

- **Entry point:** `src/main.py`
- **Modular design:** 15+ modules
- **LangChain ReAct Agent:** `src/core/agent.py`
- **Agent Tools:** `src/core/tools.py`
- **Schema caching:** `src/core/schema_loader.py`
- **UI Components:** `src/components/`
- **Database:** `src/database/`
- **Utils:** `src/utils/`

### Migration timeline:

- **Trước:** Single file `app/chatbot.py`
- **Sau:** Modular structure `src/*`
- **Dockerfile:** Đã update để chạy `src/main.py`

### Nếu cần reference code cũ:

File này được giữ lại chỉ để tham khảo. **KHÔNG** sử dụng trong production.

---

**Ngày deprecated:** December 11, 2025
**Thay thế bởi:** `src/` modular architecture
