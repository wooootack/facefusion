import inspect
import itertools
import shutil
import signal
import sys
from time import time

import numpy

from facefusion import benchmarker, cli_helper, content_analyser, face_classifier, face_detector, face_landmarker, face_masker, face_recognizer, hash_helper, logger, process_manager, state_manager, video_manager, voice_extractor, wording
from facefusion.args import apply_args, collect_job_args, reduce_job_args, reduce_step_args
from facefusion.common_helper import get_first
from facefusion.content_analyser import analyse_image, analyse_video
from facefusion.download import conditional_download_hashes, conditional_download_sources
from facefusion.exit_helper import hard_exit, signal_exit
from facefusion.face_analyser import get_average_face, get_many_faces, get_one_face
from facefusion.face_selector import sort_and_filter_faces
from facefusion.face_store import append_reference_face, clear_reference_faces, get_reference_faces
from facefusion.ffmpeg import copy_image, extract_frames, finalize_image, merge_video, replace_audio, restore_audio
from facefusion.filesystem import filter_audio_paths, get_file_name, is_image, is_video, resolve_file_paths, resolve_file_pattern
from facefusion.jobs import job_helper, job_manager, job_runner
from facefusion.jobs.job_list import compose_job_list
from facefusion.memory import limit_system_memory
from facefusion.processors.core import get_processors_modules
from facefusion.program import create_program
from facefusion.program_helper import validate_args
from facefusion.temp_helper import clear_temp_directory, create_temp_directory, get_temp_file_path, move_temp_file, resolve_temp_frame_paths
from facefusion.types import Args, ErrorCode
from facefusion.vision import pack_resolution, read_image, read_static_images, read_video_frame, restrict_image_resolution, restrict_trim_frame, restrict_video_fps, restrict_video_resolution, unpack_resolution


def cli() -> None:
	if pre_check():
		signal.signal(signal.SIGINT, signal_exit)
		program = create_program()

		if validate_args(program):
			args = vars(program.parse_args())
			apply_args(args, state_manager.init_item)

			if state_manager.get_item('command'):
				logger.init(state_manager.get_item('log_level'))
				route(args)
			else:
				program.print_help()
		else:
			hard_exit(2)
	else:
		hard_exit(2)


def route(args : Args) -> None:
	system_memory_limit = state_manager.get_item('system_memory_limit')

	if system_memory_limit and system_memory_limit > 0:
		limit_system_memory(system_memory_limit)

	if state_manager.get_item('command') == 'force-download':
		error_code = force_download()
		return hard_exit(error_code)

	if state_manager.get_item('command') == 'benchmark':
		if not common_pre_check() or not processors_pre_check() or not benchmarker.pre_check():
			return hard_exit(2)
		benchmarker.render()

	if state_manager.get_item('command') in [ 'job-list', 'job-create', 'job-submit', 'job-submit-all', 'job-delete', 'job-delete-all', 'job-add-step', 'job-remix-step', 'job-insert-step', 'job-remove-step' ]:
		if not job_manager.init_jobs(state_manager.get_item('jobs_path')):
			hard_exit(1)
		error_code = route_job_manager(args)
		hard_exit(error_code)

	if state_manager.get_item('command') == 'run':
		import facefusion.uis.core as ui

		if not common_pre_check() or not processors_pre_check():
			return hard_exit(2)
		for ui_layout in ui.get_ui_layouts_modules(state_manager.get_item('ui_layouts')):
			if not ui_layout.pre_check():
				return hard_exit(2)
		ui.init()
		ui.launch()

	if state_manager.get_item('command') == 'headless-run':
		if not job_manager.init_jobs(state_manager.get_item('jobs_path')):
			hard_exit(1)
		error_core = process_headless(args)
		hard_exit(error_core)

	if state_manager.get_item('command') == 'batch-run':
		if not job_manager.init_jobs(state_manager.get_item('jobs_path')):
			hard_exit(1)
		error_core = process_batch(args)
		hard_exit(error_core)

	if state_manager.get_item('command') in [ 'job-run', 'job-run-all', 'job-retry', 'job-retry-all' ]:
		if not job_manager.init_jobs(state_manager.get_item('jobs_path')):
			hard_exit(1)
		error_code = route_job_runner()
		hard_exit(error_code)


def pre_check() -> bool:
	if sys.version_info < (3, 10):
		logger.error(wording.get('python_not_supported').format(version = '3.10'), __name__)
		return False

	if not shutil.which('curl'):
		logger.error(wording.get('curl_not_installed'), __name__)
		return False

	if not shutil.which('ffmpeg'):
		logger.error(wording.get('ffmpeg_not_installed'), __name__)
		return False
	return True


def common_pre_check() -> bool:
	common_modules =\
	[
		content_analyser,
		face_classifier,
		face_detector,
		face_landmarker,
		face_masker,
		face_recognizer,
		voice_extractor
	]

	content_analyser_content = inspect.getsource(content_analyser).encode()
	is_valid = hash_helper.create_hash(content_analyser_content) == 'b159fd9d'
	logger.debug('Content analyser hash check: ' + str(is_valid), __name__)

	for module in common_modules:
		logger.debug('Checking module: ' + module.__name__, __name__)
		if not module.pre_check():
			logger.debug('Module check failed: ' + module.__name__, __name__)
			return False
		logger.debug('Module check passed: ' + module.__name__, __name__)

	return True


def processors_pre_check() -> bool:
	processors = state_manager.get_item('processors')
	logger.debug('Checking processors: ' + str(processors), __name__)
	for processor_module in get_processors_modules(processors):
		logger.debug('Checking processor module: ' + processor_module.__name__, __name__)
		if not processor_module.pre_check():
			logger.debug('Processor module check failed: ' + processor_module.__name__, __name__)
			return False
		logger.debug('Processor module check passed: ' + processor_module.__name__, __name__)
	return True


def force_download() -> ErrorCode:
	common_modules =\
	[
		content_analyser,
		face_classifier,
		face_detector,
		face_landmarker,
		face_masker,
		face_recognizer,
		voice_extractor
	]
	available_processors = [ get_file_name(file_path) for file_path in resolve_file_paths('facefusion/processors/modules') ]
	processor_modules = get_processors_modules(available_processors)

	for module in common_modules + processor_modules:
		if hasattr(module, 'create_static_model_set'):
			for model in module.create_static_model_set(state_manager.get_item('download_scope')).values():
				model_hash_set = model.get('hashes')
				model_source_set = model.get('sources')

				if model_hash_set and model_source_set:
					if not conditional_download_hashes(model_hash_set) or not conditional_download_sources(model_source_set):
						return 1

	return 0


def route_job_manager(args : Args) -> ErrorCode:
	if state_manager.get_item('command') == 'job-list':
		job_headers, job_contents = compose_job_list(state_manager.get_item('job_status'))

		if job_contents:
			cli_helper.render_table(job_headers, job_contents)
			return 0
		return 1

	if state_manager.get_item('command') == 'job-create':
		if job_manager.create_job(state_manager.get_item('job_id')):
			logger.info(wording.get('job_created').format(job_id = state_manager.get_item('job_id')), __name__)
			return 0
		logger.error(wording.get('job_not_created').format(job_id = state_manager.get_item('job_id')), __name__)
		return 1

	if state_manager.get_item('command') == 'job-submit':
		if job_manager.submit_job(state_manager.get_item('job_id')):
			logger.info(wording.get('job_submitted').format(job_id = state_manager.get_item('job_id')), __name__)
			return 0
		logger.error(wording.get('job_not_submitted').format(job_id = state_manager.get_item('job_id')), __name__)
		return 1

	if state_manager.get_item('command') == 'job-submit-all':
		if job_manager.submit_jobs(state_manager.get_item('halt_on_error')):
			logger.info(wording.get('job_all_submitted'), __name__)
			return 0
		logger.error(wording.get('job_all_not_submitted'), __name__)
		return 1

	if state_manager.get_item('command') == 'job-delete':
		if job_manager.delete_job(state_manager.get_item('job_id')):
			logger.info(wording.get('job_deleted').format(job_id = state_manager.get_item('job_id')), __name__)
			return 0
		logger.error(wording.get('job_not_deleted').format(job_id = state_manager.get_item('job_id')), __name__)
		return 1

	if state_manager.get_item('command') == 'job-delete-all':
		if job_manager.delete_jobs(state_manager.get_item('halt_on_error')):
			logger.info(wording.get('job_all_deleted'), __name__)
			return 0
		logger.error(wording.get('job_all_not_deleted'), __name__)
		return 1

	if state_manager.get_item('command') == 'job-add-step':
		step_args = reduce_step_args(args)

		if job_manager.add_step(state_manager.get_item('job_id'), step_args):
			logger.info(wording.get('job_step_added').format(job_id = state_manager.get_item('job_id')), __name__)
			return 0
		logger.error(wording.get('job_step_not_added').format(job_id = state_manager.get_item('job_id')), __name__)
		return 1

	if state_manager.get_item('command') == 'job-remix-step':
		step_args = reduce_step_args(args)

		if job_manager.remix_step(state_manager.get_item('job_id'), state_manager.get_item('step_index'), step_args):
			logger.info(wording.get('job_remix_step_added').format(job_id = state_manager.get_item('job_id'), step_index = state_manager.get_item('step_index')), __name__)
			return 0
		logger.error(wording.get('job_remix_step_not_added').format(job_id = state_manager.get_item('job_id'), step_index = state_manager.get_item('step_index')), __name__)
		return 1

	if state_manager.get_item('command') == 'job-insert-step':
		step_args = reduce_step_args(args)

		if job_manager.insert_step(state_manager.get_item('job_id'), state_manager.get_item('step_index'), step_args):
			logger.info(wording.get('job_step_inserted').format(job_id = state_manager.get_item('job_id'), step_index = state_manager.get_item('step_index')), __name__)
			return 0
		logger.error(wording.get('job_step_not_inserted').format(job_id = state_manager.get_item('job_id'), step_index = state_manager.get_item('step_index')), __name__)
		return 1

	if state_manager.get_item('command') == 'job-remove-step':
		if job_manager.remove_step(state_manager.get_item('job_id'), state_manager.get_item('step_index')):
			logger.info(wording.get('job_step_removed').format(job_id = state_manager.get_item('job_id'), step_index = state_manager.get_item('step_index')), __name__)
			return 0
		logger.error(wording.get('job_step_not_removed').format(job_id = state_manager.get_item('job_id'), step_index = state_manager.get_item('step_index')), __name__)
		return 1
	return 1


def route_job_runner() -> ErrorCode:
	if state_manager.get_item('command') == 'job-run':
		logger.info(wording.get('running_job').format(job_id = state_manager.get_item('job_id')), __name__)
		if job_runner.run_job(state_manager.get_item('job_id'), process_step):
			logger.info(wording.get('processing_job_succeed').format(job_id = state_manager.get_item('job_id')), __name__)
			return 0
		logger.info(wording.get('processing_job_failed').format(job_id = state_manager.get_item('job_id')), __name__)
		return 1

	if state_manager.get_item('command') == 'job-run-all':
		logger.info(wording.get('running_jobs'), __name__)
		if job_runner.run_jobs(process_step, state_manager.get_item('halt_on_error')):
			logger.info(wording.get('processing_jobs_succeed'), __name__)
			return 0
		logger.info(wording.get('processing_jobs_failed'), __name__)
		return 1

	if state_manager.get_item('command') == 'job-retry':
		logger.info(wording.get('retrying_job').format(job_id = state_manager.get_item('job_id')), __name__)
		if job_runner.retry_job(state_manager.get_item('job_id'), process_step):
			logger.info(wording.get('processing_job_succeed').format(job_id = state_manager.get_item('job_id')), __name__)
			return 0
		logger.info(wording.get('processing_job_failed').format(job_id = state_manager.get_item('job_id')), __name__)
		return 1

	if state_manager.get_item('command') == 'job-retry-all':
		logger.info(wording.get('retrying_jobs'), __name__)
		if job_runner.retry_jobs(process_step, state_manager.get_item('halt_on_error')):
			logger.info(wording.get('processing_jobs_succeed'), __name__)
			return 0
		logger.info(wording.get('processing_jobs_failed'), __name__)
		return 1
	return 2


def process_headless(args : Args) -> ErrorCode:
	job_id = job_helper.suggest_job_id('headless')
	step_args = reduce_step_args(args)

	if job_manager.create_job(job_id) and job_manager.add_step(job_id, step_args) and job_manager.submit_job(job_id) and job_runner.run_job(job_id, process_step):
		return 0
	return 1


def process_batch(args : Args) -> ErrorCode:
	job_id = job_helper.suggest_job_id('batch')
	step_args = reduce_step_args(args)
	job_args = reduce_job_args(args)
	source_paths = resolve_file_pattern(job_args.get('source_pattern'))
	target_paths = resolve_file_pattern(job_args.get('target_pattern'))

	if job_manager.create_job(job_id):
		if source_paths and target_paths:
			for index, (source_path, target_path) in enumerate(itertools.product(source_paths, target_paths)):
				step_args['source_paths'] = [ source_path ]
				step_args['target_path'] = target_path
				step_args['output_path'] = job_args.get('output_pattern').format(index = index)
				if not job_manager.add_step(job_id, step_args):
					return 1
			if job_manager.submit_job(job_id) and job_runner.run_job(job_id, process_step):
				return 0

		if not source_paths and target_paths:
			for index, target_path in enumerate(target_paths):
				step_args['target_path'] = target_path
				step_args['output_path'] = job_args.get('output_pattern').format(index = index)
				if not job_manager.add_step(job_id, step_args):
					return 1
			if job_manager.submit_job(job_id) and job_runner.run_job(job_id, process_step):
				return 0
	return 1


def process_step(job_id : str, step_index : int, step_args : Args) -> bool:
	logger.debug('Starting process_step for job_id: ' + str(job_id) + ', step_index: ' + str(step_index), __name__)
	clear_reference_faces()
	step_total = job_manager.count_step_total(job_id)
	logger.debug('Step total: ' + str(step_total), __name__)
	step_args.update(collect_job_args())
	apply_args(step_args, state_manager.set_item)
	logger.debug('Applied step arguments', __name__)

	logger.info(wording.get('processing_step').format(step_current = step_index + 1, step_total = step_total), __name__)
	logger.debug('Running common_pre_check and processors_pre_check', __name__)
	if common_pre_check() and processors_pre_check():
		logger.debug('Pre-checks passed, starting conditional_process', __name__)
		error_code = conditional_process()
		logger.debug('conditional_process returned error_code: ' + str(error_code), __name__)
		return error_code == 0
	else:
		logger.debug('Pre-checks failed', __name__)
	return False


def conditional_process() -> ErrorCode:
	start_time = time()
	logger.debug('Starting conditional_process', __name__)

	for processor_module in get_processors_modules(state_manager.get_item('processors')):
		logger.debug('Running pre_process for: ' + processor_module.__name__, __name__)
		if not processor_module.pre_process('output'):
			logger.debug('pre_process failed for: ' + processor_module.__name__, __name__)
			return 2
		logger.debug('pre_process completed for: ' + processor_module.__name__, __name__)

	logger.debug('Starting conditional_append_reference_faces', __name__)
	conditional_append_reference_faces()
	logger.debug('Completed conditional_append_reference_faces', __name__)

	target_path = state_manager.get_item('target_path')
	logger.debug('Target path: ' + str(target_path), __name__)
	logger.debug('is_image: ' + str(is_image(target_path)), __name__)
	logger.debug('is_video: ' + str(is_video(target_path)), __name__)

	if is_image(target_path):
		logger.debug('Processing as image', __name__)
		error_code = process_image(start_time)
		logger.debug('process_image returned error_code: ' + str(error_code), __name__)
		return error_code
	if is_video(target_path):
		logger.debug('Processing as video', __name__)
		error_code = process_video(start_time)
		logger.debug('process_video returned error_code: ' + str(error_code), __name__)
		return error_code

	logger.debug('No valid target found', __name__)
	return 0


def conditional_append_reference_faces() -> None:
	face_selector_mode = state_manager.get_item('face_selector_mode')
	logger.debug('Face selector mode: ' + str(face_selector_mode), __name__)

	if 'reference' in face_selector_mode and not get_reference_faces():
		logger.debug('Appending reference faces', __name__)
		source_frames = read_static_images(state_manager.get_item('source_paths'))
		source_faces = get_many_faces(source_frames)
		logger.debug('Source faces count: ' + str(len(source_faces)), __name__)
		source_face = get_average_face(source_faces)
		logger.debug('Source face found: ' + str(source_face is not None), __name__)

		target_path = state_manager.get_item('target_path')
		if is_video(target_path):
			logger.debug('Reading video frame for reference', __name__)
			reference_frame = read_video_frame(target_path, state_manager.get_item('reference_frame_number'))
		else:
			logger.debug('Reading image for reference', __name__)
			reference_frame = read_image(target_path)

		reference_faces = sort_and_filter_faces(get_many_faces([ reference_frame ]))
		logger.debug('Reference faces count: ' + str(len(reference_faces)), __name__)
		reference_face = get_one_face(reference_faces, state_manager.get_item('reference_face_position'))
		logger.debug('Reference face found: ' + str(reference_face is not None), __name__)
		append_reference_face('origin', reference_face)

		if source_face and reference_face:
			logger.debug('Creating abstract reference frames', __name__)
			for processor_module in get_processors_modules(state_manager.get_item('processors')):
				abstract_reference_frame = processor_module.get_reference_frame(source_face, reference_face, reference_frame)
				if numpy.any(abstract_reference_frame):
					abstract_reference_faces = sort_and_filter_faces(get_many_faces([ abstract_reference_frame ]))
					abstract_reference_face = get_one_face(abstract_reference_faces, state_manager.get_item('reference_face_position'))
					append_reference_face(processor_module.__name__, abstract_reference_face)
		logger.debug('Reference faces processing completed', __name__)
	else:
		logger.debug('Skipping reference faces processing', __name__)


def process_image(start_time : float) -> ErrorCode:
	logger.debug('Starting process_image', __name__)
	target_path = state_manager.get_item('target_path')
	logger.debug('Analysing image: ' + str(target_path), __name__)
	if analyse_image(target_path):
		logger.debug('Image analysis failed', __name__)
		return 3
	logger.debug('Image analysis completed', __name__)

	logger.debug(wording.get('clearing_temp'), __name__)
	clear_temp_directory(target_path)
	logger.debug(wording.get('creating_temp'), __name__)
	create_temp_directory(target_path)

	process_manager.start()
	temp_image_resolution = pack_resolution(restrict_image_resolution(state_manager.get_item('target_path'), unpack_resolution(state_manager.get_item('output_image_resolution'))))
	logger.info(wording.get('copying_image').format(resolution = temp_image_resolution), __name__)
	if copy_image(state_manager.get_item('target_path'), temp_image_resolution):
		logger.debug(wording.get('copying_image_succeed'), __name__)
	else:
		logger.error(wording.get('copying_image_failed'), __name__)
		process_manager.end()
		return 1

	temp_image_path = get_temp_file_path(state_manager.get_item('target_path'))
	logger.debug('Temp image path: ' + str(temp_image_path), __name__)

	processors = state_manager.get_item('processors')
	logger.debug('Processing with processors: ' + str(processors), __name__)
	for processor_module in get_processors_modules(processors):
		logger.debug('Starting processor: ' + processor_module.__name__, __name__)
		logger.info(wording.get('processing'), processor_module.__name__)
		processor_module.process_image(state_manager.get_item('source_paths'), temp_image_path, temp_image_path)
		logger.debug('Completed processor: ' + processor_module.__name__, __name__)
		processor_module.post_process()
		logger.debug('Post-processed: ' + processor_module.__name__, __name__)

	if is_process_stopping():
		logger.debug('Process stopping detected', __name__)
		process_manager.end()
		return 4

	logger.debug('Starting image finalization', __name__)
	logger.info(wording.get('finalizing_image').format(resolution = state_manager.get_item('output_image_resolution')), __name__)
	output_path = state_manager.get_item('output_path')
	if finalize_image(state_manager.get_item('target_path'), output_path, state_manager.get_item('output_image_resolution')):
		logger.debug(wording.get('finalizing_image_succeed'), __name__)
	else:
		logger.warn(wording.get('finalizing_image_skipped'), __name__)

	logger.debug(wording.get('clearing_temp'), __name__)
	clear_temp_directory(state_manager.get_item('target_path'))

	logger.debug('Checking output file: ' + str(output_path), __name__)
	if is_image(output_path):
		seconds = '{:.2f}'.format((time() - start_time) % 60)
		logger.info(wording.get('processing_image_succeed').format(seconds = seconds), __name__)
		logger.debug('Image processing completed successfully', __name__)
	else:
		logger.error(wording.get('processing_image_failed'), __name__)
		logger.debug('Image processing failed - output file not found', __name__)
		process_manager.end()
		return 1
	process_manager.end()
	logger.debug('process_image completed with success', __name__)
	return 0


def process_video(start_time : float) -> ErrorCode:
	logger.debug('Starting process_video', __name__)
	target_path = state_manager.get_item('target_path')
	logger.debug('Target video path: ' + str(target_path), __name__)

	trim_frame_start, trim_frame_end = restrict_trim_frame(target_path, state_manager.get_item('trim_frame_start'), state_manager.get_item('trim_frame_end'))
	logger.debug('Trim frames: start=' + str(trim_frame_start) + ', end=' + str(trim_frame_end), __name__)

	logger.debug('Analysing video', __name__)
	if analyse_video(target_path, trim_frame_start, trim_frame_end):
		logger.debug('Video analysis failed', __name__)
		return 3
	logger.debug('Video analysis completed', __name__)

	logger.debug(wording.get('clearing_temp'), __name__)
	clear_temp_directory(target_path)
	logger.debug(wording.get('creating_temp'), __name__)
	create_temp_directory(target_path)

	process_manager.start()
	logger.debug('Process manager started', __name__)

	temp_video_resolution = pack_resolution(restrict_video_resolution(target_path, unpack_resolution(state_manager.get_item('output_video_resolution'))))
	temp_video_fps = restrict_video_fps(target_path, state_manager.get_item('output_video_fps'))
	logger.debug('Video settings: resolution=' + str(temp_video_resolution) + ', fps=' + str(temp_video_fps), __name__)

	logger.info(wording.get('extracting_frames').format(resolution = temp_video_resolution, fps = temp_video_fps), __name__)
	logger.debug('Starting frame extraction', __name__)
	if extract_frames(target_path, temp_video_resolution, temp_video_fps, trim_frame_start, trim_frame_end):
		logger.debug(wording.get('extracting_frames_succeed'), __name__)
	else:
		if is_process_stopping():
			logger.debug('Process stopping during frame extraction', __name__)
			process_manager.end()
			return 4
		logger.error(wording.get('extracting_frames_failed'), __name__)
		logger.debug('Frame extraction failed', __name__)
		process_manager.end()
		return 1

	logger.debug('Resolving temp frame paths', __name__)
	temp_frame_paths = resolve_temp_frame_paths(target_path)
	logger.debug('Temp frame paths count: ' + str(len(temp_frame_paths) if temp_frame_paths else 0), __name__)

	if temp_frame_paths:
		logger.debug('Processing video frames with processors', __name__)
		processors = state_manager.get_item('processors')
		for processor_module in get_processors_modules(processors):
			logger.debug('Starting video processor: ' + processor_module.__name__, __name__)
			logger.info(wording.get('processing'), processor_module.__name__)
			processor_module.process_video(state_manager.get_item('source_paths'), temp_frame_paths)
			logger.debug('Completed video processor: ' + processor_module.__name__, __name__)
			processor_module.post_process()
			logger.debug('Post-processed video: ' + processor_module.__name__, __name__)
		if is_process_stopping():
			logger.debug('Process stopping during video processing', __name__)
			return 4
	else:
		logger.error(wording.get('temp_frames_not_found'), __name__)
		logger.debug('No temp frames found for video processing', __name__)
		process_manager.end()
		return 1

	logger.debug('Starting video merging', __name__)
	logger.info(wording.get('merging_video').format(resolution = state_manager.get_item('output_video_resolution'), fps = state_manager.get_item('output_video_fps')), __name__)
	if merge_video(target_path, temp_video_fps, state_manager.get_item('output_video_resolution'), state_manager.get_item('output_video_fps'), trim_frame_start, trim_frame_end):
		logger.debug(wording.get('merging_video_succeed'), __name__)
	else:
		if is_process_stopping():
			logger.debug('Process stopping during video merging', __name__)
			process_manager.end()
			return 4
		logger.error(wording.get('merging_video_failed'), __name__)
		logger.debug('Video merging failed', __name__)
		process_manager.end()
		return 1

	output_path = state_manager.get_item('output_path')
	output_audio_volume = state_manager.get_item('output_audio_volume')
	logger.debug('Audio volume: ' + str(output_audio_volume), __name__)

	if output_audio_volume == 0:
		logger.debug('Skipping audio processing', __name__)
		logger.info(wording.get('skipping_audio'), __name__)
		move_temp_file(target_path, output_path)
		logger.debug('Moved temp file to output', __name__)
	else:
		logger.debug('Processing audio', __name__)
		source_audio_path = get_first(filter_audio_paths(state_manager.get_item('source_paths')))
		logger.debug('Source audio path: ' + str(source_audio_path), __name__)

		if source_audio_path:
			logger.debug('Replacing audio', __name__)
			if replace_audio(target_path, source_audio_path, output_path):
				video_manager.clear_video_pool()
				logger.debug(wording.get('replacing_audio_succeed'), __name__)
			else:
				video_manager.clear_video_pool()
				if is_process_stopping():
					logger.debug('Process stopping during audio replacement', __name__)
					process_manager.end()
					return 4
				logger.warn(wording.get('replacing_audio_skipped'), __name__)
				logger.debug('Audio replacement failed, moving temp file', __name__)
				move_temp_file(target_path, output_path)
		else:
			logger.debug('Restoring audio', __name__)
			if restore_audio(target_path, output_path, trim_frame_start, trim_frame_end):
				video_manager.clear_video_pool()
				logger.debug(wording.get('restoring_audio_succeed'), __name__)
			else:
				video_manager.clear_video_pool()
				if is_process_stopping():
					logger.debug('Process stopping during audio restoration', __name__)
					process_manager.end()
					return 4
				logger.warn(wording.get('restoring_audio_skipped'), __name__)
				logger.debug('Audio restoration failed, moving temp file', __name__)
				move_temp_file(target_path, output_path)

	logger.debug(wording.get('clearing_temp'), __name__)
	clear_temp_directory(target_path)

	logger.debug('Checking final output video: ' + str(output_path), __name__)
	if is_video(output_path):
		seconds = '{:.2f}'.format((time() - start_time))
		logger.info(wording.get('processing_video_succeed').format(seconds = seconds), __name__)
		logger.debug('Video processing completed successfully', __name__)
	else:
		logger.error(wording.get('processing_video_failed'), __name__)
		logger.debug('Video processing failed - output file not found', __name__)
		process_manager.end()
		return 1
	process_manager.end()
	logger.debug('process_video completed with success', __name__)
	return 0


def is_process_stopping() -> bool:
	if process_manager.is_stopping():
		logger.debug('Process is stopping, ending process manager', __name__)
		process_manager.end()
		logger.info(wording.get('processing_stopped'), __name__)
	is_pending = process_manager.is_pending()
	logger.debug('Process pending status: ' + str(is_pending), __name__)
	return is_pending
