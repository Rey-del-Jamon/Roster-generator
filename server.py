import os
import datetime
from http.server import SimpleHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import fitz  # PyMuPDF

def catch_errors(func):
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except Exception as e:
            import traceback
            err_str = traceback.format_exc()
            print("GENERATION ERROR:", err_str)
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Server Error during generation:\n{err_str}".encode('utf-8'))
    return wrapper

def round_dt_to_5(dt):
    # Standard 5 minute rounding
    discard = datetime.timedelta(minutes=dt.minute % 5,
                                 seconds=dt.second,
                                 microseconds=dt.microsecond)
    dt -= discard
    if discard >= datetime.timedelta(minutes=2.5):
        dt += datetime.timedelta(minutes=5)
    return dt

def fmtTime(t):
    return t.strftime('%H%M')

class RosterHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, must-revalidate')
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

    @catch_errors
    def do_GET(self):
        parsed = urlparse(self.path)
        
        if parsed.path == '/':
            self.path = '/index.html'
            return super().do_GET()
        elif parsed.path in ('/index.html', '/styles.css', '/app.js'):
            return super().do_GET()
            
        if parsed.path == '/generate':
            query = parse_qs(parsed.query)
            # Enforce passcode protection
            passcode = query.get('passcode', [''])[0]
            if passcode != '21908':
                self.send_response(401)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Unauthorized: Invalid passcode.")
                return
            
            mode = query.get('mode', ['report'])[0]
            
            # Open document and keep a clean source for copying
            doc = fitz.open(r'media__1781707928976.pdf')
            doc_src = fitz.open(r'media__1781707928976.pdf')
            page = doc[0]
            
            time_str = query.get('time', [''])[0]
            if time_str:
                try:
                    t_str = time_str.replace('Z', '+00:00')
                    now = datetime.datetime.fromisoformat(t_str)
                except ValueError:
                    now = datetime.datetime.now(datetime.timezone.utc)
            else:
                now = datetime.datetime.now(datetime.timezone.utc)
                
            tz_offset_str = query.get('tzOffset', [''])[0]
            try:
                tz_offset_min = int(tz_offset_str) if tz_offset_str else 0
            except ValueError:
                tz_offset_min = 0
            
            local_now = now - datetime.timedelta(minutes=tz_offset_min)
            
            if mode == 'report':
                dt_ci = round_dt_to_5(now) + datetime.timedelta(hours=1)
                dt_dep1 = dt_ci + datetime.timedelta(hours=1, minutes=5)
                dt_arr1 = dt_dep1 + datetime.timedelta(hours=1, minutes=15)
                dt_dep2 = dt_arr1 + datetime.timedelta(minutes=45)
                dt_arr2 = dt_dep2 + datetime.timedelta(hours=1, minutes=15)
                dt_co = dt_arr2 + datetime.timedelta(minutes=30)
            else:
                dt_co = round_dt_to_5(now) - datetime.timedelta(minutes=30)
                dt_arr2 = dt_co - datetime.timedelta(minutes=30)
                dt_dep2 = dt_arr2 - datetime.timedelta(hours=1, minutes=15)
                dt_arr1 = dt_dep2 - datetime.timedelta(minutes=45)
                dt_dep1 = dt_arr1 - datetime.timedelta(hours=1, minutes=15)
                dt_ci = dt_dep1 - datetime.timedelta(hours=1, minutes=5)

            ci_time = dt_ci.time()
            dep1 = dt_dep1.time()
            arr1 = dt_arr1.time()
            dep2 = dt_dep2.time()
            arr2 = dt_arr2.time()
            co_time = dt_co.time()
            
            fdp_duration = dt_co - dt_ci
            fdp_hours = fdp_duration.seconds // 3600
            fdp_minutes = (fdp_duration.seconds // 60) % 60
            fdp_str = f"[FDP {fdp_hours:02d}:{fdp_minutes:02d}]"
            
            monday_curr = local_now - datetime.timedelta(days=local_now.weekday())
            sunday_4_weeks = monday_curr + datetime.timedelta(days=27)
            thursday_prev = monday_curr - datetime.timedelta(days=4)
            
            def fmtDate(d):
                return d.strftime("%d%b%y")
                
            str_mon_curr = fmtDate(monday_curr)
            str_sun_4 = fmtDate(sunday_4_weeks)
            str_thu_prev = fmtDate(thursday_prev)
                
            base_orig = datetime.datetime(2026, 6, 8)
            orig_strs = [(base_orig + datetime.timedelta(days=i)).strftime('%a%d') for i in range(28)]
            new_strs = [(monday_curr + datetime.timedelta(days=i)).strftime('%a%d') for i in range(28)]
            date_map = dict(zip(orig_strs, new_strs))
            
            diff_days = (local_now.date() - monday_curr.date()).days
            target_orig_str = orig_strs[diff_days]
                
            words = page.get_text("words")
            target_rect = None
            for w in words:
                if w[4] == target_orig_str and w[0] < 500:
                    target_rect = fitz.Rect(w[:4])
                    break
                
            if not target_rect:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b"Date not found in roster")
                return

            my_max = 294.5 if target_rect.y0 < 260 else 842
            needed_visual_height = 36 if mode == 'report' else 44
            next_mx_top = 0
            if diff_days + 1 < len(orig_strs):
                next_orig_str = orig_strs[diff_days + 1]
                next_rect = None
                for w in words:
                    if w[4] == next_orig_str and w[0] < 500:
                        next_rect = fitz.Rect(w[:4])
                        break
                
                if next_rect:
                    if (target_rect.y0 < 260 and next_rect.y0 < 260) or (target_rect.y0 >= 260 and next_rect.y0 >= 260):
                        next_mx_top = next_rect.x1 + 2
            
            orig_visual_height = target_rect.x1 - next_mx_top
            shift_dy = needed_visual_height - orig_visual_height
            
            for w in words:
                if w[4] == target_orig_str:
                    continue
                if next_mx_top <= w[0] <= target_rect.x1 + 1 and target_rect.y0 - 2 <= w[1] <= my_max + 2:
                    rect = fitz.Rect(w[0] - 0.2, w[1] - 0.2, w[2] + 0.2, w[3] - 0.8)
                    page.draw_rect(rect, color=(1,1,1), fill=(1,1,1))
            
            if shift_dy != 0 and next_mx_top > 0:
                safe_y0 = target_rect.y0 + 0.5
                safe_ymax = my_max - 2.0
                clip_rect = fitz.Rect(0, safe_y0, next_mx_top, safe_ymax)
                target_shift_rect = fitz.Rect(0 - shift_dy, safe_y0, next_mx_top - shift_dy, safe_ymax)
                union_min_x = min(0 - shift_dy, 0)
                union_max_x = max(next_mx_top, next_mx_top - shift_dy)
                union_rect = fitz.Rect(union_min_x, safe_y0, union_max_x, safe_ymax)
                page.draw_rect(union_rect, color=(1,1,1), fill=(1,1,1))
                page.show_pdf_page(target_shift_rect, doc_src, 0, clip=clip_rect)

            tSize = 5.977
            font_ref = 'cour'
            for f in page.get_fonts():
                if 'NimbusMonL-Regu' in f[3]:
                    font_ref = f[4]
                    break
            
            base_mx = target_rect.x0
            base_my = target_rect.y0
            lineH = 7.5
            
            def draw(text, offset_x, row_offset):
                if not text: return
                mx = base_mx - (row_offset * lineH)
                my = base_my + offset_x
                morph = (fitz.Point(mx, my), fitz.Matrix(0, -1, 1, 0, 0, 0))
                text_color = (35/255.0, 31/255.0, 32/255.0)
                page.insert_text(fitz.Point(mx, my), text, fontname=font_ref, fontsize=tSize, color=text_color, morph=morph)

            draw('C/I', 31.2, 0)
            draw('AMS', 103.2, 0)
            draw(fmtTime(ci_time), 125.2, 0)
            
            draw('KL 1021', 42.0, 1)
            draw('AMS', 103.2, 1)
            draw(fmtTime(dep1), 125.2, 1)
            draw(fmtTime(arr1), 145.9, 1)
            draw('LHR', 167.9, 1)
            draw('E90', 186.6, 1)
            
            draw('KL 1022', 42.0, 2)
            draw('LHR', 103.2, 2)
            draw(fmtTime(dep2), 125.2, 2)
            draw(fmtTime(arr2), 145.9, 2)
            draw('AMS', 167.9, 2)
            draw('E90', 186.6, 2)
            
            draw('C/O', 31.2, 3)
            draw(fmtTime(co_time), 125.2, 3)
            draw('AMS', 145.9, 3)
            draw(fdp_str, 214.6, 3)
            
            rect_tl = fitz.Rect(532.0, 96.0, 543.0, 206.0)
            page.draw_rect(rect_tl, color=(1,1,1), fill=(1,1,1))
            
            rect_tr = fitz.Rect(541.0, 725.0, 551.0, 762.0)
            page.draw_rect(rect_tr, color=(1,1,1), fill=(1,1,1))
            
            def drawAbs(text, mx, my, tSize):
                if not text: return
                morph = (fitz.Point(mx, my), fitz.Matrix(0, -1, 1, 0, 0, 0))
                text_color = (35/255.0, 31/255.0, 32/255.0)
                page.insert_text(fitz.Point(mx, my), text, fontname=font_ref, fontsize=tSize, color=text_color, morph=morph)
            
            page.draw_rect(fitz.Rect(530, 90, 541, 240), color=(1,1,1), fill=(1,1,1)) 
            page.draw_rect(fitz.Rect(541, 720, 551, 765), color=(1,1,1), fill=(1,1,1)) 
            
            drawAbs(str_mon_curr, 535.08, 97.18, 9.962)
            drawAbs('-', 535.08, 145.06, 9.962)
            drawAbs(str_sun_4, 535.08, 162.94, 9.962)
            drawAbs(str_thu_prev, 543.72, 726.70, 7.970)

            for w in words:
                orig_str = w[4]
                if orig_str in date_map:
                    new_str = date_map[orig_str]
                    
                    shift_offset = 0
                    if target_rect and w[0] < next_mx_top and abs(w[1] - target_rect.y0) < 10:
                        shift_offset = -shift_dy
                        
                    if w[0] > 500:
                        rect = fitz.Rect(w[0] + 0.2, w[1] + 1.0, w[2] - 0.2, w[3] - 1.0)
                        page.draw_rect(rect, color=(1,1,1), fill=(1,1,1))
                        drawAbs(new_str, w[0] + shift_offset + 1.30, w[1], 5.977)
                        
                        if orig_str == target_orig_str:
                            day_y0 = w[1] - 2
                            day_y1 = w[3] + 2
                            for hw in words:
                                if day_y0 <= hw[1] <= day_y1 and 490 <= hw[0] <= 515:
                                    hw_rect = fitz.Rect(hw[0] + 0.8, hw[1] - 0.2, hw[2] + 0.2, hw[3] + 0.2)
                                    page.draw_rect(hw_rect, color=(1,1,1), fill=(1,1,1))
                            
                            ci_str = dt_ci.strftime('%H%M')
                            co_str = dt_co.strftime('%H%M')
                            drawAbs('FlD', 511.32, w[1] + 1.8, 5.977)
                            drawAbs(ci_str, 503.88, w[1] + 1.8, 5.977)
                            drawAbs(co_str, 497.88, w[1] + 1.8, 5.977)
                        
                        continue
                    else:
                        rect = fitz.Rect(w[0]-0.5 + shift_offset, w[1]-0.5, w[2]+0.5 + shift_offset, w[3]-0.5)
                        
                    page.draw_rect(rect, color=(1,1,1), fill=(1,1,1))
                    drawAbs(new_str, w[0] + shift_offset + 1.30, w[1], 5.977)

            pdf_bytes = doc.write(garbage=3, deflate=True)
            
            self.send_response(200)
            self.send_header('Content-type', 'application/pdf')
            self.send_header('Content-Disposition', 'inline; filename="roster_generated.pdf"')
            self.send_header('Content-Length', str(len(pdf_bytes)))
            self.end_headers()
            self.wfile.write(pdf_bytes)
            return
            
        self.send_response(404)
        self.end_headers()

if __name__ == '__main__':
    import shutil
    src = r'C:\Users\ocsel\.gemini\antigravity\brain\d9186601-3f45-4232-ab00-e04274196300\media__1781707928976.pdf'
    if not os.path.exists('media__1781707928976.pdf'):
        try:
            shutil.copy(src, 'media__1781707928976.pdf')
        except:
            pass

    HTTPServer.allow_reuse_address = True
    port = int(os.environ.get('PORT', 8080))
    server = HTTPServer(('0.0.0.0', port), RosterHandler)
    print(f"Server running on port {port}")
    server.serve_forever()
