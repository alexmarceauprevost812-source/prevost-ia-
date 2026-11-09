import ast
import contextlib
import importlib.machinery
import importlib.util
import io
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
import installer

loader=importlib.machinery.SourceFileLoader('rea_prevost',str(Path(installer.__file__).with_name('rea-prevost')))
spec=importlib.util.spec_from_loader(loader.name,loader)
launcher=importlib.util.module_from_spec(spec)
loader.exec_module(launcher)

python_loader=importlib.machinery.SourceFileLoader('prevost_rea_script',str(Path(installer.__file__).with_name('prevost-rea')))
python_spec=importlib.util.spec_from_loader(python_loader.name,python_loader)
python_script=importlib.util.module_from_spec(python_spec)
python_loader.exec_module(python_script)


class ShortcutTests(unittest.TestCase):
    def test_preview_backup_and_idempotence(self):
        with tempfile.TemporaryDirectory() as d,contextlib.redirect_stdout(io.StringIO()):
            root=Path(d);gui=root/'rea-gui'
            gui.write_text(installer.OLD+'\n');gui.chmod(0o755)
            installer.install(root)
            self.assertEqual(gui.read_text(),installer.OLD+'\n')
            self.assertFalse((root/'rea-prevost').exists())
            backup=installer.install(root,True)
            self.assertEqual((backup/'rea-gui').read_text(),installer.OLD+'\n')
            self.assertIn(installer.NEW,gui.read_text())
            compile(gui.read_text(),str(gui),'exec')
            self.assertTrue((root/'rea-prevost').stat().st_mode & 0o111)
            installer.install(root,True)
            self.assertEqual(gui.read_text().count(installer.NEW),1)

    def test_upgrade_previous_chat_shortcut(self):
        with tempfile.TemporaryDirectory() as d,contextlib.redirect_stdout(io.StringIO()):
            root=Path(d);gui=root/'rea-gui';gui.write_text(installer.LEGACY+'\n')
            installer.install(root,True)
            self.assertIn(installer.NEW,gui.read_text())
            self.assertNotIn(installer.LEGACY,gui.read_text())

    def test_unknown_gui_stays_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            gui=Path(d)/'rea-gui';gui.write_text('autre version')
            with self.assertRaises(ValueError):installer.install(Path(d),True)
            self.assertEqual(gui.read_text(),'autre version')

    def test_gui_project_and_command_arguments_preserved(self):
        node=next(n for n in ast.parse(installer.NEW).body if isinstance(n,ast.FunctionDef))
        file_dialog=Mock();file_dialog.askdirectory.return_value='/tmp/projet avec espaces'
        process=Mock();namespace={'filedialog':file_dialog,'shutil':Mock(),'subprocess':process,'log':Mock(),'__file__':'/tmp/local/bin/rea-gui'}
        namespace['shutil'].which.return_value='/usr/bin/xfce4-terminal'
        exec(compile(ast.Module(body=[node],type_ignores=[]),'gui-test','exec'),namespace)
        namespace['launch_rea_prevost']()
        args=process.Popen.call_args.args[0]
        self.assertEqual(shlex.split(args[-1]),['/tmp/local/bin/rea-prevost','--project','/tmp/projet avec espaces'])
        file_dialog.askdirectory.return_value='';process.reset_mock()
        namespace['launch_rea_prevost']()
        process.Popen.assert_not_called()

    def test_local_hosts_and_remote_rejection(self):
        self.assertEqual(launcher.local_host('127.0.0.1:11435'),'http://127.0.0.1:11435')
        self.assertEqual(launcher.local_host('http://[::1]:11434'),'http://[::1]:11434')
        for value in ('https://outside.invalid','http://user:secret@localhost:11434','http://localhost:11434/path','file:///tmp/x'):
            with self.assertRaises(ValueError):launcher.local_host(value)

    def test_capabilities_not_extracted_from_system_prompt(self):
        text='Model\n  tools\nCapabilities\n  completion\nParameters\n  tools\nSystem\n  tools\n'
        self.assertEqual(launcher.capabilities(text),['completion'])

    def test_preview_does_not_contact_ollama_or_exec(self):
        with tempfile.TemporaryDirectory() as d,patch.object(launcher.subprocess,'run',side_effect=AssertionError('no process')),patch.object(launcher.os,'execvpe',side_effect=AssertionError('no exec')),contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(launcher.main(['--project',d,'--apercu']),0)
            self.assertIn('codex',out.getvalue())
            self.assertIn('prevost:latest',out.getvalue())

    def test_codex_launch_with_model_project_and_validations(self):
        result=Mock(returncode=0,stdout='Capabilities\n completion\n tools\nParameters\n',stderr='')
        with tempfile.TemporaryDirectory() as d,patch.object(launcher.shutil,'which',return_value='/fake/bin'),patch.object(launcher.subprocess,'run',return_value=result) as run,patch.object(launcher.os,'execvpe') as execute:
            self.assertEqual(launcher.main(['--project',d,'--host','127.0.0.1:11435','Corrige les tests']),0)
            execute.assert_called_once()
            program,args,env=execute.call_args.args
            self.assertEqual(program,'codex')
            self.assertEqual(args[args.index('--model')+1],'prevost:latest')
            self.assertEqual(args[args.index('--cd')+1],d)
            self.assertEqual(args[args.index('--sandbox')+1],'workspace-write')
            self.assertEqual(args[args.index('--ask-for-approval')+1],'on-request')
            self.assertIn('http://127.0.0.1:11435/v1',' '.join(args))
            self.assertEqual(env['OLLAMA_HOST'],'http://127.0.0.1:11435')
            self.assertIn('Corrige les tests',args[-1])
            self.assertNotIn('--dangerously-bypass-approvals-and-sandbox',args)
            run.assert_called_once()
            self.assertEqual(run.call_args.args[0],['ollama','show','prevost:latest'])

    def test_unsupported_tools_no_fallback_or_pull(self):
        result=Mock(returncode=0,stdout='Capabilities\n completion\nParameters\n',stderr='')
        with tempfile.TemporaryDirectory() as d,patch.object(launcher.shutil,'which',return_value='/fake/bin'),patch.object(launcher.subprocess,'run',return_value=result) as run,patch.object(launcher.os,'execvpe') as execute,contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(launcher.main(['--project',d]),2)
            execute.assert_not_called()
            self.assertEqual(run.call_args.args[0],['ollama','show','prevost:latest'])

    def test_diagnostic_never_launches_codex(self):
        result=Mock(returncode=0,stdout='Capabilities\n tools\n',stderr='')
        with tempfile.TemporaryDirectory() as d,patch.object(launcher.shutil,'which',return_value='/fake/bin'),patch.object(launcher.subprocess,'run',return_value=result),patch.object(launcher.os,'execvpe') as execute,contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(launcher.main(['--project',d,'--diagnostic']),0)
            self.assertIn('"inference_verified": false',out.getvalue())
            execute.assert_not_called()

    def test_environment_denial_not_reported_as_missing_model(self):
        result=Mock(returncode=1,stdout='',stderr='socket: operation not permitted')
        with tempfile.TemporaryDirectory() as d,patch.object(launcher.shutil,'which',return_value='/fake/bin'),patch.object(launcher.subprocess,'run',return_value=result),patch.object(launcher.os,'execvpe') as execute,contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(launcher.main(['--project',d,'--diagnostic']),1)
            self.assertIn('restriction_environnement',out.getvalue())
            execute.assert_not_called()

    def test_launcher_real_help(self):
        result=subprocess.run([str(Path(installer.__file__).with_name('rea-prevost')),'--help'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0)
        self.assertIn('--project',result.stdout)

    def test_title_says_rea_with_local_prevost_and_keeps_codex(self):
        fresh='root.title("REA — LEXOS PRO")\nLabel(header, text="   LEXOS PRO  |  AGENT IA LOCAL")\n'
        updated=installer.apply_theme(fresh)
        self.assertIn(installer.WINDOW_TITLE,updated)
        self.assertIn('REA avec PRÉVOST local',updated)
        self.assertIn('Codex gardé',updated)
        self.assertNotIn('CODEX LOCAL',updated)
        self.assertEqual(installer.apply_theme(updated),updated)

    def test_install_updates_title_of_already_themed_gui_once(self):
        old_themed='root.title("PRÉVOST — rea-prevost")\nLabel(header, text="   rea-prevost  |  CODEX LOCAL")\n'
        with tempfile.TemporaryDirectory() as d,contextlib.redirect_stdout(io.StringIO()):
            root=Path(d);gui=root/'rea-gui';gui.write_text(installer.OLD+'\n'+old_themed)
            installer.install(root,True)
            first=gui.read_text()
            self.assertIn(installer.WINDOW_TITLE,first)
            self.assertIn('REA avec PRÉVOST local',first)
            self.assertNotIn('CODEX LOCAL',first)
            self.assertIn('button("rea-prevost", launch_rea_prevost)',first)
            self.assertIn('button("prevost-rea", launch_prevost_rea)',first)
            installer.install(root,True)
            self.assertEqual(gui.read_text(),first)
            compile(first,str(gui),'exec')

    def test_rea_icon_launcher_and_desktop_copy(self):
        with tempfile.TemporaryDirectory() as d,contextlib.redirect_stdout(io.StringIO()) as out,patch.object(installer,'trust') as trust:
            root=Path(d)/'bin';share=Path(d)/'share';desk=Path(d)/'Bureau'
            root.mkdir();desk.mkdir()
            gui=root/'rea-gui';gui.write_text(installer.OLD+'\n')
            installer.install(root,True,None,share,desk)
            icon=share/'icons'/'rea.svg';launcher=share/'applications'/'rea-interface.desktop';copy=desk/'REA.desktop'
            self.assertEqual(icon.read_text(encoding='utf-8'),Path(installer.__file__).with_name('rea.svg').read_text(encoding='utf-8'))
            for entry in (launcher,copy):
                text=entry.read_text(encoding='utf-8')
                self.assertIn('Name=REA\n',text)
                self.assertIn(f'Icon={icon}\n',text)
                self.assertIn(f'Exec=python3 "{gui}"\n',text)
                self.assertTrue(entry.stat().st_mode & 0o111)
            trust.assert_called_once_with(copy)
            self.assertIn('Icône REA',out.getvalue())
            first=(icon.read_bytes(),launcher.read_bytes(),copy.read_bytes())
            backup=installer.install(root,True,None,share,desk)
            self.assertEqual((icon.read_bytes(),launcher.read_bytes(),copy.read_bytes()),first)
            self.assertEqual((backup/'REA.desktop').read_bytes(),first[2])

    def test_without_share_dir_no_desktop_files_are_written(self):
        with tempfile.TemporaryDirectory() as d,contextlib.redirect_stdout(io.StringIO()),patch.object(installer,'trust') as trust:
            root=Path(d);gui=root/'rea-gui';gui.write_text(installer.OLD+'\n')
            installer.install(root,True)
            trust.assert_not_called()
            self.assertEqual(sorted(p.name for p in root.iterdir() if p.is_file()),['prevost-rea','rea-gui','rea-prevost'])

    def test_desktop_symlink_refused_and_missing_desktop_dir_skipped(self):
        with tempfile.TemporaryDirectory() as d,contextlib.redirect_stdout(io.StringIO()),patch.object(installer,'trust'):
            root=Path(d)/'bin';share=Path(d)/'share';desk=Path(d)/'Bureau'
            root.mkdir();desk.mkdir()
            gui=root/'rea-gui';gui.write_text(installer.OLD+'\n')
            (desk/'REA.desktop').symlink_to(root/'rea-gui')
            with self.assertRaises(ValueError):installer.install(root,True,None,share,desk)
            self.assertFalse((share/'icons'/'rea.svg').exists())
            (desk/'REA.desktop').unlink()
            installer.install(root,True,None,share,Path(d)/'inexistant')
            self.assertTrue((share/'applications'/'rea-interface.desktop').exists())
            self.assertFalse((Path(d)/'inexistant').exists())

    def test_exec_quote_and_icon_file(self):
        self.assertEqual(installer.exec_quote('/tmp/a b/50%/x"y'),'"/tmp/a b/50%%/x\\"y"')
        import xml.dom.minidom
        svg=xml.dom.minidom.parse(str(Path(installer.__file__).with_name('rea.svg')))
        self.assertEqual(svg.documentElement.getAttribute('viewBox'),'0 0 256 256')
        self.assertIn('REA',svg.documentElement.toxml())

    def test_theme_keeps_black_white_and_syntax_colors(self):
        import plistlib
        theme=plistlib.loads(Path(installer.__file__).with_name('prevost-noir.tmTheme').read_bytes())
        colors=theme['settings'][0]['settings']
        self.assertEqual(colors['background'],'#000000')
        self.assertEqual(colors['foreground'],'#FFFFFF')
        self.assertGreater(len({item['settings'].get('foreground') for item in theme['settings'][1:]}),3)
        source='BG = "#050505"\nWHITE = "#F5F5F5"\nORANGE = "#FF7900"\neditor.tag_configure("string", foreground=GREEN)\n'
        updated=installer.apply_theme(source)
        self.assertIn('BG = "#000000"',updated)
        self.assertIn('WHITE = "#FFFFFF"',updated)
        self.assertIn('ORANGE = "#E00000"',updated)
        self.assertIn('tag_configure("string", foreground=GREEN)',updated)

    def test_installer_saves_theme_without_touching_config(self):
        with tempfile.TemporaryDirectory() as d,contextlib.redirect_stdout(io.StringIO()):
            root=Path(d);(root/'rea-gui').write_text(installer.OLD+'\n')
            theme_dir=root/'codex/themes'
            config=root/'codex/config.toml';config.parent.mkdir()
            config.write_text('model = "existing"\n')
            installer.install(root,True,theme_dir)
            self.assertTrue((theme_dir/'prevost-noir.tmTheme').is_file())
            self.assertEqual(config.read_text(),'model = "existing"\n')

    def test_ptyxis_fallback_uses_documented_argument_separator(self):
        node=next(n for n in ast.parse(installer.NEW).body if isinstance(n,ast.FunctionDef))
        dialog=Mock();dialog.askdirectory.return_value='/tmp/project'
        which=Mock();which.which.side_effect=lambda name:'/usr/bin/ptyxis' if name=='ptyxis' else None
        process=Mock();namespace={'filedialog':dialog,'shutil':which,'subprocess':process,'log':Mock(),'__file__':'/tmp/bin/rea-gui'}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'gui-test','exec'),namespace)
        namespace['launch_rea_prevost']()
        self.assertEqual(process.Popen.call_args.args[0],['/usr/bin/ptyxis','--new-window','--working-directory','/tmp/project','--','/tmp/bin/rea-prevost','--project','/tmp/project'])

    def test_terminal_session_color_sequences_are_complete(self):
        result=Mock(returncode=0,stdout='Capabilities\n tools\n',stderr='')
        capture=io.StringIO();capture.isatty=lambda:True
        with tempfile.TemporaryDirectory() as d,patch.object(launcher.shutil,'which',return_value='/fake/bin'),patch.object(launcher.subprocess,'run',return_value=result),patch.object(launcher.os,'execvpe'),contextlib.redirect_stdout(capture):
            self.assertEqual(launcher.main(['--project',d]),0)
        self.assertIn('\033]10;#FFFFFF\007',capture.getvalue())
        self.assertIn('\033]11;#000000\007',capture.getvalue())
        self.assertIn('\033[31mPRÉVOST',capture.getvalue())


class PythonButtonTests(unittest.TestCase):
    """Bouton prevost-rea : PRÉVOST Python lancé depuis REA, en plus du bouton Codex."""

    def install_in(self, root, content):
        (root/'rea-gui').write_text(content)
        with contextlib.redirect_stdout(io.StringIO()):
            return installer.install(root,True)

    def test_both_buttons_installed_once_and_script_bound_to_repository(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.install_in(root,installer.OLD+'\n')
            gui=(root/'rea-gui').read_text()
            compile(gui,'rea-gui','exec')
            self.assertEqual(gui.count(installer.NEW),1)
            self.assertEqual(gui.count(installer.PYTHON_BLOCK),1)
            self.assertIn('button("rea-prevost", launch_rea_prevost)',gui)
            self.assertIn('button("prevost-rea", launch_prevost_rea)',gui)
            script=root/'prevost-rea'
            self.assertTrue(script.stat().st_mode & 0o111)
            repository=str(Path(installer.__file__).resolve().parents[1])
            self.assertIn('DEPOT = '+repr(repository),script.read_text())
            self.assertNotIn(installer.DEPOT_LINE,script.read_text())
            with contextlib.redirect_stdout(io.StringIO()):
                installer.install(root,True)
            gui=(root/'rea-gui').read_text()
            self.assertEqual((gui.count(installer.NEW),gui.count(installer.PYTHON_BLOCK)),(1,1))

    def test_gui_already_patched_for_codex_only_gets_second_button(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);backup=self.install_in(root,installer.NEW+'\n')
            gui=(root/'rea-gui').read_text()
            self.assertEqual(gui.count(installer.NEW),1)
            self.assertEqual(gui.count(installer.PYTHON_BLOCK),1)
            self.assertEqual((backup/'rea-gui').read_text(),installer.NEW+'\n')

    def test_gui_with_previous_prevost_ia_name_is_migrated_to_prevost_rea(self):
        self.assertIn('prevost-ia',installer.PYTHON_BLOCK_V1)
        self.assertNotIn('prevost-rea',installer.PYTHON_BLOCK_V1)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.install_in(root,installer.NEW+'\n\n'+installer.PYTHON_BLOCK_V1+'\n')
            gui=(root/'rea-gui').read_text()
            self.assertNotIn('prevost-ia',gui)
            self.assertEqual((gui.count(installer.NEW),gui.count(installer.PYTHON_BLOCK)),(1,1))
            compile(gui,'rea-gui','exec')

    def test_unknown_gui_still_refused_and_nothing_written(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'rea-gui').write_text('autre version')
            with self.assertRaises(ValueError):installer.install(root,True)
            self.assertFalse((root/'prevost-rea').exists())
            self.assertFalse((root/'rea-prevost').exists())

    def test_symlinked_script_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'rea-gui').write_text(installer.OLD+'\n')
            (root/'prevost-rea').symlink_to(root/'ailleurs')
            with self.assertRaises(ValueError):installer.install(root,True)

    def test_button_passes_project_with_spaces_and_cancel_runs_nothing(self):
        node=next(n for n in ast.parse(installer.PYTHON_BLOCK).body if isinstance(n,ast.FunctionDef))
        dialog=Mock();dialog.askdirectory.return_value='/tmp/projet avec espaces'
        process=Mock();namespace={'filedialog':dialog,'shutil':Mock(),'subprocess':process,'log':Mock(),'__file__':'/tmp/local/bin/rea-gui'}
        namespace['shutil'].which.return_value='/usr/bin/xfce4-terminal'
        exec(compile(ast.Module(body=[node],type_ignores=[]),'gui-test','exec'),namespace)
        namespace['launch_prevost_rea']()
        args=process.Popen.call_args.args[0]
        self.assertEqual(shlex.split(args[-1]),['/tmp/local/bin/prevost-rea','--project','/tmp/projet avec espaces'])
        dialog.askdirectory.return_value='';process.reset_mock()
        namespace['launch_prevost_rea']()
        process.Popen.assert_not_called()

    def test_model_comes_from_environment_only_when_not_given(self):
        build=python_script.build_args
        self.assertEqual(build(['--project','/p'],{}),['--project','/p'])
        self.assertEqual(build(['--project','/p'],{'PREVOST_MODEL':'qwen3:8b'}),['--project','/p','--model','qwen3:8b'])
        self.assertEqual(build(['--model','autre'],{'PREVOST_MODEL':'qwen3:8b'}),['--model','autre'])
        self.assertEqual(build(['--model=autre'],{'PREVOST_MODEL':'qwen3:8b'}),['--model=autre'])

    def run_script(self,script,args,cwd):
        env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}
        env.pop('PREVOST_MODEL',None)
        return subprocess.run([str(script),*args],capture_output=True,text=True,cwd=cwd,env=env,stdin=subprocess.DEVNULL,timeout=30)

    def test_installed_script_runs_prevost_from_any_directory(self):
        with tempfile.TemporaryDirectory() as d,tempfile.TemporaryDirectory() as elsewhere:
            root=Path(d);self.install_in(root,installer.OLD+'\n')
            result=self.run_script(root/'prevost-rea',['--help'],elsewhere)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('--corrections',result.stdout)

    def test_repository_copy_also_runs_without_installation(self):
        result=self.run_script(Path(installer.__file__).with_name('prevost-rea'),['--help'],tempfile.gettempdir())
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('--project',result.stdout)

    def test_startup_error_keeps_terminal_open_and_returns_failure(self):
        with tempfile.TemporaryDirectory() as d,tempfile.TemporaryDirectory() as elsewhere:
            root=Path(d);self.install_in(root,installer.OLD+'\n')
            result=self.run_script(root/'prevost-rea',['--diagnostic','--ollama','http://127.0.0.1:1','--http-timeout','1'],elsewhere)
            self.assertEqual(result.returncode,1)
            self.assertIn('Erreur',result.stdout)
            self.assertIn('Entrée pour fermer',result.stdout)
