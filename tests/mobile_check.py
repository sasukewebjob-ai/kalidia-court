"""Mobile browser regression checks. Run: python tests/mobile_check.py"""
import functools
import http.server
import json
from pathlib import Path
import threading

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main():
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(ROOT)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=2, service_workers='block')
        context.route('https://**/*', lambda route: route.abort())
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(f'http://127.0.0.1:{server.server_port}/', wait_until='load')

        def check(name, expression):
            ok = page.evaluate(expression)
            results.append({'test': name, 'pass': bool(ok)})
            print(name, 'PASS' if ok else 'FAIL', flush=True)

        def reset():
            page.evaluate('''() => {initState(); lastVariant={}; sel=[]; clearPairSel(); undoStack=[]; render();}''')

        def tap(selector, fraction=0.5):
            el = page.locator(selector).first
            el.scroll_into_view_if_needed()
            box = el.bounding_box()
            page.touchscreen.tap(box['x'] + box['width'] * fraction, box['y'] + box['height'] / 2)

        for width in [320, 360, 390, 430, 844]:
            page.set_viewport_size({'width': width, 'height': 844 if width < 500 else 390})
            check(f'no horizontal overflow {width}px', 'document.documentElement.scrollWidth <= innerWidth')
        page.set_viewport_size({'width': 390, 'height': 844})
        for fraction in [0.2, 0.5, 0.8, 0.9]:
            reset()
            tap('#pool .chip', fraction)
            check(f'roster tap {fraction}', 'sel.length === 1 && !people.some(p=>p.absent)')
        tap('#assignBar .ab-btn')
        check('tap assign', 'courts[0].pids.length === 1 && sel.length === 0')
        tap('.cmem')
        tap('#pairHint .ph-btn')
        check('return to pool', 'courts[0].pids.length === 0')
        tap('#pool .chip')
        page.get_by_role('button', name='🚫 欠席へ (1)', exact=True).tap()
        check('mark absent', 'people.filter(p=>p.absent).length === 1')
        tap('.to-return')
        check('restore attendance', '!people.some(p=>p.absent)')
        page.evaluate('''() => {people.slice(0,2).forEach(p=>assign(p.id,'c0')); render();}''')
        tap('.cmem', 0.5)
        tap('.cmem:nth-child(2)', 0.5)
        check('tap pair creation', 'courts[0].pairs.length === 1')
        for fraction in [0.5, 0.8, 0.9]:
            page.evaluate('''() => {sel=[]; clearPairSel(); courts[0].pairs=[[people[0].id,people[1].id]]; render();}''')
            tap('.pair-group .cmem:nth-child(3)', fraction)
            check(f'paired member tap {fraction}', 'courts[0].pairs.length === 1 && sel.length === 2')
        if page.evaluate('sel.length === 2'):
            page.locator('#assignBar .ab-btn').nth(1).tap()
            check('pair transfer', 'courts[1].pairs.length===1 && courts[1].pids.length===2 && courts[0].pids.length===0')
            page.evaluate('undoLast()')
            check('undo pair transfer', 'courts[0].pairs.length===1 && courts[1].pids.length===0')
        tap('.pair-group .cmem:nth-child(3)', 0.9)
        page.get_by_role('button', name='ペア解除 (1組)', exact=True).tap()
        check('explicit mobile unpair', 'courts[0].pairs.length===0 && courts[0].pids.length===2')

        for layout_id in page.evaluate('LAYOUTS.map(l=>l.id)') + ['single']:
            page.evaluate('(id) => applyLayout(id)', layout_id)
            check(f'layout {layout_id} keeps participants', 'courts.flatMap(c=>c.pids).length===2 && courts.every(c=>c.pids.every(pid=>findPerson(pid).courtId===c.id))')
        page.evaluate('swapCourts()')
        check('court swap maintains assignment references', 'courts.every(c=>c.pids.every(pid=>findPerson(pid).courtId===c.id))')
        page.evaluate("addTournamentPair(people[0].id,people[1].id); applyTournamentPairs();")
        check('tournament pair apply', 'courts.reduce((n,c)=>n+c.pairs.length,0)===1')
        page.evaluate('releaseTournamentPairs()')
        check('tournament pair release', 'courts.every(c=>c.pairs.length===0)')

        # ── 面の配置（上段 C D ／ 下段 A B）とレイアウト ──
        helpers = '''() => {
            window.rectOf = name => [...document.querySelectorAll('#grid .card')]
                .find(c => c.querySelector('.cname').value === name).getBoundingClientRect();
            window.cellCourt = cells => courts.find(c => c.cells.join() === cells);
            window.noOverlap = () => {
                const rs = [...document.querySelectorAll('#grid .card')].map(el => el.getBoundingClientRect());
                return rs.every((a, i) => rs.every((b, j) => j <= i ||
                    Math.min(a.right, b.right) - Math.max(a.left, b.left) <= 1 ||
                    Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) <= 1));
            };
            window.fullWidth = name => {
                const g = document.getElementById('grid').getBoundingClientRect(), r = rectOf(name);
                return Math.abs(r.left - g.left) < 2 && Math.abs(r.right - g.right) < 2;
            };
        }'''
        page.add_init_script(f'({helpers})()')  # リロード後も使えるように
        page.evaluate(helpers)
        reset()
        check('default layout C D / A B', '''(() => { const C=rectOf('コートC'), D=rectOf('コートD'), A=rectOf('コートA'), B=rectOf('コートB');
            return Math.abs(C.top-D.top)<2 && Math.abs(A.top-B.top)<2 && C.top<A.top && C.left<D.left && Math.abs(C.left-A.left)<2 && Math.abs(D.left-B.left)<2; })()''')
        check('default variant bar hidden', "document.getElementById('variantBar').hidden")
        layout_checks = {
            '2+2-h': "fullWidth('コートC+D') && fullWidth('コートA+B') && rectOf('コートC+D').top < rectOf('コートA+B').top",
            '2+2-v': "rectOf('コートA+C').left < rectOf('コートB+D').left && Math.abs(rectOf('コートA+C').top - rectOf('コートB+D').top) < 2",
            '2+1+1-top': "fullWidth('コートC+D') && rectOf('コートC+D').top < rectOf('コートA').top && rectOf('コートA').left < rectOf('コートB').left",
            '2+1+1-bottom': "fullWidth('コートA+B') && rectOf('コートC').top < rectOf('コートA+B').top",
            '2+1+1-left': "rectOf('コートA+C').left < rectOf('コートD').left && rectOf('コートD').top < rectOf('コートB').top && rectOf('コートA+C').height > rectOf('コートD').height * 1.5",
            '2+1+1-right': "rectOf('コートB+D').left > rectOf('コートC').left && rectOf('コートC').top < rectOf('コートA').top && rectOf('コートB+D').height > rectOf('コートC').height * 1.5",
            '1+3-A': "fullWidth('コートB+C+D') && fullWidth('コートA') && rectOf('コートB+C+D').top < rectOf('コートA').top",
            '1+3-B': "fullWidth('コートA+C+D') && rectOf('コートA+C+D').top < rectOf('コートB').top",
            '1+3-C': "fullWidth('コートC') && fullWidth('コートA+B+D') && rectOf('コートC').top < rectOf('コートA+B+D').top",
            '1+3-D': "fullWidth('コートD') && rectOf('コートD').top < rectOf('コートA+B+C').top",
            'all': "fullWidth('全コート') && courts.length === 1 && courts[0].max === 24",
        }
        for layout_id, expr in layout_checks.items():
            page.evaluate('(id) => applyLayout(id)', layout_id)
            check(f'layout {layout_id} placement', f"currentLayout().id === '{layout_id}' && noOverlap() && ({expr}) && courts.every(c => c.max === 6 * c.cells.length)")
            page.set_viewport_size({'width': 320, 'height': 844})
            check(f'layout {layout_id} no overflow 320px', 'document.documentElement.scrollWidth <= innerWidth')
            page.set_viewport_size({'width': 390, 'height': 844})

        reset()
        tap('.pbtn[data-layout-type="1+3"]')
        check('type button shows variants', "currentLayout().type === '1+3' && !document.getElementById('variantBar').hidden && document.querySelectorAll('#variantBar .vbtn').length === 4")
        tap('#variantBar .vbtn[data-layout="1+3-A"]')
        check('variant tap switches layout', "currentLayout().id === '1+3-A' && document.querySelector('#variantBar .vbtn.on').dataset.layout === '1+3-A'")
        tap('.pbtn[data-layout-type="single"]')
        tap('.pbtn[data-layout-type="1+3"]')
        check('type button remembers last variant', "currentLayout().id === '1+3-A'")
        page.reload()
        check('layout and remembered variant survive reload', "currentLayout().id === '1+3-A' && lastVariant['1+3'] === '1+3-A'")
        tap('.pbtn[data-layout-type="1+3"]')
        check('same type button keeps layout', "currentLayout().id === '1+3-A'")

        reset()
        page.evaluate("() => {assign(people[0].id, cellCourt('C').id); assign(people[1].id, cellCourt('B').id); render();}")
        page.evaluate("applyLayout('2+1+1-top')")
        check('merge keeps members on their courts', "findPerson(people[0].id).courtId === cellCourt('C,D').id && findPerson(people[1].id).courtId === cellCourt('B').id")
        page.evaluate("applyLayout('single')")
        check('split goes back to top-left face', "findPerson(people[0].id).courtId === cellCourt('C').id && findPerson(people[1].id).courtId === cellCourt('B').id")
        page.evaluate('undoLast()')
        check('undo layout change', "currentLayout().id === '2+1+1-top' && findPerson(people[0].id).courtId === cellCourt('C,D').id")

        reset()
        page.evaluate("() => {assign(people[0].id, cellCourt('C').id); assign(people[1].id, cellCourt('A').id); render(); swapCourts();}")
        check('swap moves members, faces stay', "findPerson(people[0].id).courtId === cellCourt('A').id && findPerson(people[1].id).courtId === cellCourt('C').id && rectOf('コートC').top < rectOf('コートA').top")
        page.evaluate("() => {applyLayout('2+1+1-top'); swapCourts();}")
        check('swap flips merged shape', "currentLayout().id === '2+1+1-bottom'")
        page.evaluate("() => {applyLayout('1+3-A'); swapCourts();}")
        check('swap flips single court', "currentLayout().id === '1+3-C'")
        page.evaluate("() => {applyLayout('single'); courts[0].name = 'ビギナー'; swapCourts();}")
        check('swap carries custom name', "cellCourt('A').name === 'ビギナー' && cellCourt('C').name === 'コートC'")
        page.evaluate("() => {applyLayout('2+2-v'); window.undoLen = undoStack.length; swapCourts();}")
        check('swap on vertical layout is no-op', "currentLayout().id === '2+2-v' && undoStack.length === window.undoLen")

        # 旧形式（cellsなし）の保存データを新しい配置へ移す
        def legacy(courts_js):
            page.evaluate('''() => { const st = {version:1, currentPreset:0, people: people.map(p=>({...p, courtId:null})),
                guests: guests.map(g=>({...g})), courts: COURTS };
                localStorage.setItem(STORAGE_KEY, JSON.stringify(st)); }'''.replace('COURTS', courts_js))
            page.reload()
        reset()
        legacy("[{id:'c0',name:'コートA',max:6,wide:false,pids:[people[0].id],pairs:[]},{id:'c1',name:'コートB',max:6,wide:false,pids:[],pairs:[]},{id:'c2',name:'コートC',max:6,wide:false,pids:[people[1].id],pairs:[]},{id:'c3',name:'コートD',max:6,wide:false,pids:[],pairs:[]}]")
        check('legacy 4 courts follow court names', "currentLayout().id === 'single' && findPerson(people[0].id).courtId === cellCourt('A').id && findPerson(people[1].id).courtId === cellCourt('C').id && rectOf('コートC').top < rectOf('コートA').top")
        legacy("[{id:'c0',name:'コートA（2面）',max:12,wide:true,pids:[people[0].id],pairs:[]},{id:'c1',name:'コートB（2面）',max:12,wide:true,pids:[],pairs:[]}]")
        check('legacy 2 courts become C+D / A+B', "currentLayout().id === '2+2-h' && cellCourt('C,D').name === 'コートC+D' && findPerson(people[0].id).courtId === cellCourt('C,D').id")
        legacy("[{id:'c0',name:'コートB',max:6,wide:false,pids:[people[0].id],pairs:[]},{id:'c1',name:'自由',max:6,wide:false,pids:[],pairs:[]},{id:'c2',name:'コートA（2面）',max:12,wide:true,pids:[people[1].id],pairs:[]}]")
        check('legacy swapped 3 courts keep screen positions', "currentLayout().id === '2+1+1-bottom' && cellCourt('C').name === 'コートC' && cellCourt('D').name === '自由' && findPerson(people[0].id).courtId === cellCourt('C').id && findPerson(people[1].id).courtId === cellCourt('A,B').id")

        # 選択のオン/オフが色ではっきり分かる（タップ後に:hoverの色が残らない）
        reset()
        tap('#pool .chip')
        page.wait_for_timeout(250)
        check('selected chip is filled', "getComputedStyle(document.querySelector('#pool .chip.selected')).backgroundColor === 'rgb(4, 120, 87)'")
        tap('#pool .chip')
        page.wait_for_timeout(250)
        check('deselected chip loses the color', "(() => { const el = document.querySelector('#pool .chip'); return sel.length === 0 && getComputedStyle(el).backgroundColor === 'rgb(232, 238, 244)'; })()")
        page.evaluate("() => {assign(people[0].id,'c0'); assign(people[1].id,'c0'); makePair('c0',people[0].id,people[1].id); sel=[people[0].id]; render();}")
        page.wait_for_timeout(250)
        check('selected pair member is filled', "(() => { const els = document.querySelectorAll('.pair-group .cmem'); return getComputedStyle(els[0]).backgroundColor === 'rgb(4, 120, 87)' && getComputedStyle(els[1]).backgroundColor !== 'rgb(4, 120, 87)'; })()")

        reset()
        page.evaluate("() => {applyLayout('all'); people.slice(0,24).forEach(p=>assign(p.id,'c0')); for (let i=0;i<24;i+=2) makePair('c0',people[i].id,people[i+1].id); render();}")
        check('12 pairs on 4 faces get distinct colors', "courts[0].pairs.length === 12 && new Set([...document.querySelectorAll('.pair-group')].map(el => el.style.borderColor)).size === 12")

        reset()
        page.evaluate('''() => {people.slice(0,8).forEach(p=>assign(p.id,'c0')); makePair('c0',people[6].id,people[7].id); render();}''')
        page.reload()
        check('overflow members and pair survive reload', 'courts[0].pids.length===8 && courts[0].pairs.length===1')

        reset()
        page.evaluate('''() => {guests[0].enabled=true; guests[0].name='Guest'; sel=['g1']; render(); toggleGuest(0); assignSelectionToCourt('c0');}''')
        check('disabled guest cannot be assigned from stale selection', "courts[0].pids.length===0 && sel.length===0")

        reset()
        page.evaluate('''() => {guests[0].enabled=true; guests[0].name='<b>Guest</b>'; render();}''')
        check('guest name rendered literally', "document.querySelector('#pool .guest .cn').textContent === '<b>Guest</b>' && !document.querySelector('#pool .guest .cn b')")
        page.evaluate("assign('g1','c0'); render()")
        page.locator('.g-inp').first.fill('New guest')
        check('guest rename updates court immediately', "document.querySelector('.cmem .cn').textContent==='New guest'")
        page.locator('.g-inp').first.fill('')
        check('empty guest clears court and selection', 'courts[0].pids.length===0 && sel.length===0')
        page.locator('.g-inp').first.fill('Restored guest')
        tap('#pool .chip.guest')
        check('first tap after guest edit selects guest', "sel.includes('g1')")

        reset()
        page.evaluate("assign(people[0].id,'c0'); render(); window.beforeImport=snapshot();")
        page.evaluate("importBackup(new File([JSON.stringify({app:'kalidia-court',state:{people:[],guests:[],courts:[]}})],'bad.json'))")
        page.wait_for_function("[...document.querySelectorAll('.toast')].some(t=>t.textContent.includes('バックアップファイルではありません'))")
        check('invalid backup preserves current data', 'snapshot()===window.beforeImport')
        page.on('dialog', lambda dialog: dialog.accept())
        page.evaluate("window.backupData={app:'kalidia-court',state:JSON.parse(snapshot()),tournament:{tournamentName:'Test',tournamentPairs:[]}}; resetAll(); importBackup(new File([JSON.stringify(window.backupData)],'good.json'))")
        page.wait_for_function("tournamentName==='Test'")
        check('valid backup restores data', 'courts[0].pids.length===1')

        page.evaluate("window.open=()=>null; window.capturedBackup=null; downloadBackup=(blob)=>blob.text().then(text=>window.capturedBackup=JSON.parse(text)); window.realStorageSet=Storage.prototype.setItem; Storage.prototype.setItem=()=>{throw new Error('quota test')}; assign(people[1].id,'c0'); render(); exportBackup();")
        page.wait_for_function('window.capturedBackup !== null')
        check('backup retains latest data despite save failure', 'window.capturedBackup.state.courts[0].pids.length===2')
        page.evaluate('() => {Storage.prototype.setItem=window.realStorageSet;}')

        reset()
        try:
            page.evaluate('screenshotCourts()')
        except Exception as error:
            errors.append(str(error).splitlines()[0])
        check('missing screenshot library preserves layout', "document.getElementById('grid').style.minWidth === '' && document.getElementById('courtsArea').style.width === ''")
        page.evaluate("window.html2canvas=()=>Promise.reject(new Error('capture test')); screenshotCourts()")
        check('failed capture restores layout', "!screenshotPending && document.getElementById('grid').style.minWidth === '' && document.getElementById('courtsArea').style.width === ''")
        page.evaluate("window.captureCount=0; window.html2canvas=()=>{window.captureCount++;return new Promise(resolve=>window.finishCapture=resolve)}; screenshotCourts(); screenshotCourts(); window.finishCapture({toBlob:fn=>fn(null)})")
        page.wait_for_function('!screenshotPending')
        check('double capture does not corrupt layout', "window.captureCount===1 && document.getElementById('grid').style.minWidth === ''")

        page.evaluate('''() => {initState(); people.slice(0,8).forEach(p=>assign(p.id,'c0')); makePair('c0',people[0].id,people[1].id); sel=people.slice(0,2).map(p=>p.id); render(); document.querySelectorAll('.toast').forEach(t=>t.remove());}''')
        for width in [320, 390]:
            page.set_viewport_size({'width': width, 'height': 844})
            check(f'populated layout {width}px', 'document.documentElement.scrollWidth <= innerWidth')
        page.wait_for_timeout(250)  # Let the app's 150ms entrance transitions finish for visual QA.
        page.screenshot(path=str(ROOT / 'tests' / 'mobile-review.png'), full_page=True)
        page.add_init_script("Storage.prototype.getItem=()=>{throw new Error('storage disabled')}; Storage.prototype.setItem=()=>{throw new Error('storage disabled')};")
        page.reload()
        check('app starts when browser storage unavailable', 'document.querySelectorAll("#pool .chip").length===26 && document.querySelectorAll(".card").length===4')
        check('no uncaught browser errors', f'{json.dumps(errors)}.length === 0')
        browser.close()
    server.shutdown()
    (ROOT / 'tests' / 'mobile-results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Passed {sum(r['pass'] for r in results)}/{len(results)} checks")
    if errors:
        print('Browser errors:', errors)
    return 0 if all(r['pass'] for r in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())

