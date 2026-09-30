# test-output.txt-content-example

## Command

```cmd
C:\Users\initial\Downloads\osat-run-test-001\osat-manager-python-windows-test-fixes>type test-output.txt
```

## Output example

```cmd
test_leaves_a_foreign_old_file_in_place (__main__.TestAliasCommand.test_leaves_a_foreign_old_file_in_place) ... ok
test_refusals (__main__.TestAliasCommand.test_refusals) ... ok
test_refuses_a_foreign_file (__main__.TestAliasCommand.test_refuses_a_foreign_file) ... ok
test_refuses_a_name_another_alias_uses (__main__.TestAliasCommand.test_refuses_a_name_another_alias_uses) ... ok
test_rename_a_versioned_alias (__main__.TestAliasCommand.test_rename_a_versioned_alias) ... ok
test_rename_python_and_the_manager (__main__.TestAliasCommand.test_rename_python_and_the_manager) ... ok
test_same_name_is_a_no_op (__main__.TestAliasCommand.test_same_name_is_a_no_op) ... ok
test_absent (__main__.TestAliasOwnership.test_absent) ... ok
test_foreign_files (__main__.TestAliasOwnership.test_foreign_files) ... ok
test_ours_every_format (__main__.TestAliasOwnership.test_ours_every_format) ... ok
test_symlink_is_foreign_even_to_our_own_alias (__main__.TestAliasOwnership.test_symlink_is_foreign_even_to_our_own_alias) ... skipped 'exercises POSIX modes and /bin/sh'
test_generic_alias_reads_default_key (__main__.TestAliasRendering.test_generic_alias_reads_default_key) ... ok
test_nix_alias_matches_proposal_header (__main__.TestAliasRendering.test_nix_alias_matches_proposal_header) ... ok
test_template_errors (__main__.TestAliasRendering.test_template_errors) ... ok
test_windows_aliases (__main__.TestAliasRendering.test_windows_aliases) ... ok
test_actions_are_mutually_exclusive (__main__.TestCli.test_actions_are_mutually_exclusive) ... ok
test_manager_version_reads_its_own_directory (__main__.TestCli.test_manager_version_reads_its_own_directory) ... ok
test_no_action_is_usage_error (__main__.TestCli.test_no_action_is_usage_error) ... ok
test_no_version_constant (__main__.TestCli.test_no_version_constant) ... ok
test_unknown_option_is_usage_error (__main__.TestCli.test_unknown_option_is_usage_error) ... ok
test_version_comes_from_the_version_file (__main__.TestCli.test_version_comes_from_the_version_file) ... ok
test_names_the_venv_command (__main__.TestExternallyManagedMessage.test_names_the_venv_command) ... ok
test_no_stray_or_blank_lines (__main__.TestExternallyManagedMessage.test_no_stray_or_blank_lines) ... ok
test_written_into_the_runtime (__main__.TestExternallyManagedMessage.test_written_into_the_runtime) ... ok
test_already_installed_switches_without_downloading (__main__.TestInstall.test_already_installed_switches_without_downloading) ... ok
test_asset_missing_from_sums_installs_nothing (__main__.TestInstall.test_asset_missing_from_sums_installs_nothing) ... ok
test_checksum_mismatch_installs_nothing (__main__.TestInstall.test_checksum_mismatch_installs_nothing) ... ok
test_default_track_follows_the_current_default (__main__.TestInstall.test_default_track_follows_the_current_default) ... ok
test_failed_health_check_installs_nothing (__main__.TestInstall.test_failed_health_check_installs_nothing) ... ok
test_first_install (__main__.TestInstall.test_first_install) ... ok
test_foreign_alias_stops_before_any_network_access (__main__.TestInstall.test_foreign_alias_stops_before_any_network_access) ... ok
test_installed_tree_is_owner_only (__main__.TestInstall.test_installed_tree_is_owner_only) ... skipped 'exercises POSIX modes and /bin/sh'
test_later_install_keeps_the_manager_version (__main__.TestInstall.test_later_install_keeps_the_manager_version) ... ok
test_legacy_member_checks (__main__.TestInstall.test_legacy_member_checks) ... ok
test_manager_needs_a_version_file (__main__.TestInstall.test_manager_needs_a_version_file) ... ok
test_minor_line_install_moves_python_and_keeps_other_lines (__main__.TestInstall.test_minor_line_install_moves_python_and_keeps_other_lines) ... ok
test_missing_manager_copy_is_reinstalled (__main__.TestInstall.test_missing_manager_copy_is_reinstalled) ... ok
test_offline_restore_from_archive (__main__.TestInstall.test_offline_restore_from_archive) ... ok
test_path_notes (__main__.TestInstall.test_path_notes) ... ok
test_pinned_install_makes_no_api_call (__main__.TestInstall.test_pinned_install_makes_no_api_call) ... ok
test_rename_before_install_avoids_a_collision (__main__.TestInstall.test_rename_before_install_avoids_a_collision) ... ok
test_tampered_archive_is_refused (__main__.TestInstall.test_tampered_archive_is_refused) ... ok
test_unsafe_tarball_installs_nothing (__main__.TestInstall.test_unsafe_tarball_installs_nothing) ... ok
test_windows_layout (__main__.TestInstall.test_windows_layout) ... ok
test_catalog_translates_messages_but_not_names (__main__.TestLanguage.test_catalog_translates_messages_but_not_names) ... ok
test_invalid_code_is_a_usage_error (__main__.TestLanguage.test_invalid_code_is_a_usage_error) ... ok
test_main_lang_option (__main__.TestLanguage.test_main_lang_option) ... ok
test_only_english_ships_for_now (__main__.TestLanguage.test_only_english_ships_for_now) ... ok
test_order_option_then_variable_then_system_then_english (__main__.TestLanguage.test_order_option_then_variable_then_system_then_english) ... ok
test_regional_request_falls_back_to_the_language (__main__.TestLanguage.test_regional_request_falls_back_to_the_language) ... ok
test_system_language (__main__.TestLanguage.test_system_language) ... ok
test_unavailable_requests (__main__.TestLanguage.test_unavailable_requests) ... ok
test_a_foreign_ps1_is_left_with_a_warning (__main__.TestLegacyPowerShellAliases.test_a_foreign_ps1_is_left_with_a_warning) ... ok
test_install_removes_the_old_ps1_aliases (__main__.TestLegacyPowerShellAliases.test_install_removes_the_old_ps1_aliases) ... ok
test_rename_and_remove_take_the_old_ps1_too (__main__.TestLegacyPowerShellAliases.test_rename_and_remove_take_the_old_ps1_too) ... ok
test_switch_removes_the_old_ps1_aliases (__main__.TestLegacyPowerShellAliases.test_switch_removes_the_old_ps1_aliases) ... ok
test_a_pointer_ps1_it_did_not_write_is_left (__main__.TestLegacyWindowsPointer.test_a_pointer_ps1_it_did_not_write_is_left) ... ok
test_install_writes_only_the_cmd_pointer_and_deletes_the_old_one (__main__.TestLegacyWindowsPointer.test_install_writes_only_the_cmd_pointer_and_deletes_the_old_one) ... ok
test_nothing_happens_on_posix (__main__.TestLegacyWindowsPointer.test_nothing_happens_on_posix) ... ok
test_operator_env_ps1_is_left_and_warned_about_once (__main__.TestLegacyWindowsPointer.test_operator_env_ps1_is_left_and_warned_about_once) ... ok
test_switch_alias_and_remove_delete_the_old_pointer (__main__.TestLegacyWindowsPointer.test_switch_alias_and_remove_delete_the_old_pointer) ... ok
test_exit_codes_and_log (__main__.TestMainLifecycle.test_exit_codes_and_log) ... ok
test_install_through_main (__main__.TestMainLifecycle.test_install_through_main) ... ok
test_refuses_administrator_on_windows (__main__.TestMainLifecycle.test_refuses_administrator_on_windows)
Runs on every platform: the Windows check with a stand-in for ... ok
test_refuses_root (__main__.TestMainLifecycle.test_refuses_root) ... skipped 'exercises POSIX modes and /bin/sh'
test_status_is_read_only (__main__.TestMainLifecycle.test_status_is_read_only) ... ok
test_posix_render (__main__.TestManagerAlias.test_posix_render) ... ok
test_runs_the_named_manager_on_the_default_runtime (__main__.TestManagerAlias.test_runs_the_named_manager_on_the_default_runtime) ... skipped 'exercises POSIX modes and /bin/sh'
test_windows_render (__main__.TestManagerAlias.test_windows_render) ... ok
test_write_alias_uses_manager_template (__main__.TestManagerAlias.test_write_alias_uses_manager_template) ... ok
test_a_504_then_success (__main__.TestNetworkRetries.test_a_504_then_success) ... ok
test_a_download_reset_mid_body_starts_the_file_again (__main__.TestNetworkRetries.test_a_download_reset_mid_body_starts_the_file_again) ... ok
test_a_reset_then_success (__main__.TestNetworkRetries.test_a_reset_then_success) ... ok
test_keeps_failing (__main__.TestNetworkRetries.test_keeps_failing) ... ok
test_not_retried (__main__.TestNetworkRetries.test_not_retried) ... ok
test_retries_are_not_logged_only_the_result (__main__.TestNetworkRetries.test_retries_are_not_logged_only_the_result) ... ok
test_the_default_waits (__main__.TestNetworkRetries.test_the_default_waits) ... ok
test_forms (__main__.TestParseSpec.test_forms) ... ok
test_rejects_everything_else (__main__.TestParseSpec.test_rejects_everything_else) ... ok
test_alias_files_per_platform (__main__.TestPaths.test_alias_files_per_platform) ... ok
test_display (__main__.TestPaths.test_display) ... ok
test_posix_defaults (__main__.TestPaths.test_posix_defaults) ... ok
test_posix_respects_xdg (__main__.TestPaths.test_posix_respects_xdg) ... ok
test_windows_pointer_is_local_not_roaming (__main__.TestPaths.test_windows_pointer_is_local_not_roaming) ... ok
test_both_formats_carry_same_keys_and_values (__main__.TestPointerFormats.test_both_formats_carry_same_keys_and_values) ... ok
test_cmd_syntax (__main__.TestPointerFormats.test_cmd_syntax) ... ok
test_no_powershell_pointer_format (__main__.TestPointerFormats.test_no_powershell_pointer_format) ... ok
test_parse_refuses_foreign_lines (__main__.TestPointerFormats.test_parse_refuses_foreign_lines) ... ok
test_parse_refuses_unsafe_values (__main__.TestPointerFormats.test_parse_refuses_unsafe_values) ... ok
test_parse_tolerates_comments_bom_and_case (__main__.TestPointerFormats.test_parse_tolerates_comments_bom_and_case) ... ok
test_posix_pointer_is_sourceable_by_sh (__main__.TestPointerFormats.test_posix_pointer_is_sourceable_by_sh) ... skipped 'exercises POSIX modes and /bin/sh'
test_posix_render_matches_proposal_body (__main__.TestPointerFormats.test_posix_render_matches_proposal_body) ... ok
test_posix_write_is_owner_only_and_leaves_no_temp_files (__main__.TestPointerFormats.test_posix_write_is_owner_only_and_leaves_no_temp_files) ... skipped 'exercises POSIX modes and /bin/sh'
test_proposal_example_parses (__main__.TestPointerFormats.test_proposal_example_parses) ... ok
test_read_missing_pointer_is_empty (__main__.TestPointerFormats.test_read_missing_pointer_is_empty) ... ok
test_read_names_the_file_on_error (__main__.TestPointerFormats.test_read_names_the_file_on_error) ... ok
test_refuses_pointer_dir_broader_than_owner_only (__main__.TestPointerFormats.test_refuses_pointer_dir_broader_than_owner_only) ... skipped 'exercises POSIX modes and /bin/sh'
test_round_trip_every_format (__main__.TestPointerFormats.test_round_trip_every_format) ... ok
test_unknown_alias_slot_refused (__main__.TestPointerFormats.test_unknown_alias_slot_refused) ... ok
test_unknown_keys_survive_a_rewrite (__main__.TestPointerFormats.test_unknown_keys_survive_a_rewrite) ... ok
test_windows_write_produces_one_cmd_file_with_crlf (__main__.TestPointerFormats.test_windows_write_produces_one_cmd_file_with_crlf) ... ok
test_write_failure_keeps_old_pointer_and_cleans_up (__main__.TestPointerFormats.test_write_failure_keeps_old_pointer_and_cleans_up) ... ok
test_write_refuses_invalid_record_before_touching_disk (__main__.TestPointerFormats.test_write_refuses_invalid_record_before_touching_disk) ... ok
test_alias_name_rules (__main__.TestPointerRecord.test_alias_name_rules) ... ok
test_default_alias_names (__main__.TestPointerRecord.test_default_alias_names) ... ok
test_items_order_matches_proposal (__main__.TestPointerRecord.test_items_order_matches_proposal) ... ok
test_manage_python_is_reserved_for_the_manager (__main__.TestPointerRecord.test_manage_python_is_reserved_for_the_manager) ... ok
test_minor_lines_sort_numerically (__main__.TestPointerRecord.test_minor_lines_sort_numerically) ... ok
test_rejects_default_that_disagrees_with_its_line (__main__.TestPointerRecord.test_rejects_default_that_disagrees_with_its_line) ... ok
test_rejects_duplicate_alias_names_case_insensitively (__main__.TestPointerRecord.test_rejects_duplicate_alias_names_case_insensitively) ... ok
test_rejects_non_versions (__main__.TestPointerRecord.test_rejects_non_versions) ... ok
test_rejects_rename_onto_another_default_name (__main__.TestPointerRecord.test_rejects_rename_onto_another_default_name) ... ok
test_rejects_version_on_wrong_line (__main__.TestPointerRecord.test_rejects_version_on_wrong_line) ... ok
test_rename_survives_switch (__main__.TestPointerRecord.test_rename_survives_switch) ... ok
test_switch_moves_default_and_its_line_only (__main__.TestPointerRecord.test_switch_moves_default_and_its_line_only) ... ok
test_missing_key_fails_with_a_message (__main__.TestPosixAliasEndToEnd.test_missing_key_fails_with_a_message) ... skipped 'exercises POSIX modes and /bin/sh'
test_operator_env_is_read_after_the_pointer (__main__.TestPosixAliasEndToEnd.test_operator_env_is_read_after_the_pointer) ... skipped 'exercises POSIX modes and /bin/sh'
test_passes_arguments_and_exit_status_through (__main__.TestPosixAliasEndToEnd.test_passes_arguments_and_exit_status_through) ... skipped 'exercises POSIX modes and /bin/sh'
test_switch_takes_effect_without_rewriting_alias (__main__.TestPosixAliasEndToEnd.test_switch_takes_effect_without_rewriting_alias) ... skipped 'exercises POSIX modes and /bin/sh'
test_install_ps1_hashes_with_dotnet (__main__.TestPowerShellScriptsNeedNoModulePath.test_install_ps1_hashes_with_dotnet) ... ok
test_only_built_in_cmdlets (__main__.TestPowerShellScriptsNeedNoModulePath.test_only_built_in_cmdlets) ... ok
test_the_known_offenders_are_gone (__main__.TestPowerShellScriptsNeedNoModulePath.test_the_known_offenders_are_gone) ... ok
test_first_five_keys_match_restic_order (__main__.TestProvenance.test_first_five_keys_match_restic_order) ... ok
test_manager_provenance_has_first_five_keys_only (__main__.TestProvenance.test_manager_provenance_has_first_five_keys_only) ... ok
test_missing_provenance_is_empty (__main__.TestProvenance.test_missing_provenance_is_empty) ... ok
test_owner_only (__main__.TestProvenance.test_owner_only) ... skipped 'exercises POSIX modes and /bin/sh'
test_reader_is_lenient (__main__.TestProvenance.test_reader_is_lenient) ... ok
test_reads_restic_provenance (__main__.TestProvenance.test_reads_restic_provenance) ... ok
test_refuses_bad_values (__main__.TestProvenance.test_refuses_bad_values) ... ok
test_round_trip (__main__.TestProvenance.test_round_trip) ... ok
test_runtime_fields_come_together (__main__.TestProvenance.test_runtime_fields_come_together) ... ok
test_runtime_provenance_matches_proposal (__main__.TestProvenance.test_runtime_provenance_matches_proposal) ... ok
test_timestamp_is_utc (__main__.TestProvenance.test_timestamp_is_utc) ... ok
test_uppercase_sha_is_normalised (__main__.TestProvenance.test_uppercase_sha_is_normalised) ... ok
test_exclusion_rule (__main__.TestReleaseExclusions.test_exclusion_rule) ... ok
test_first_install_checks_the_line_alias_before_downloading (__main__.TestReleaseExclusions.test_first_install_checks_the_line_alias_before_downloading) ... ok
test_first_install_end_to_end (__main__.TestReleaseExclusions.test_first_install_end_to_end) ... ok
test_first_install_takes_the_newest_stable_minor_line (__main__.TestReleaseExclusions.test_first_install_takes_the_newest_stable_minor_line) ... ok
test_free_threaded_builds_are_never_selected (__main__.TestReleaseExclusions.test_free_threaded_builds_are_never_selected) ... ok
test_minor_line_with_only_pre_releases_is_refused (__main__.TestReleaseExclusions.test_minor_line_with_only_pre_releases_is_refused) ... ok
test_pre_releases_are_never_selected (__main__.TestReleaseExclusions.test_pre_releases_are_never_selected) ... ok
test_spec_cannot_name_a_pre_release (__main__.TestReleaseExclusions.test_spec_cannot_name_a_pre_release) ... ok
test_version_search_skips_pre_releases (__main__.TestReleaseExclusions.test_version_search_skips_pre_releases) ... ok
test_build_urls (__main__.TestReleaseLookup.test_build_urls) ... ok
test_builds_in_release_ignores_variants_and_other_flavours (__main__.TestReleaseLookup.test_builds_in_release_ignores_variants_and_other_flavours) ... ok
test_minor_line_takes_newest_patch_of_latest_release (__main__.TestReleaseLookup.test_minor_line_takes_newest_patch_of_latest_release) ... ok
test_not_found (__main__.TestReleaseLookup.test_not_found) ... ok
test_parse_sha256sums (__main__.TestReleaseLookup.test_parse_sha256sums) ... ok
test_pinned_needs_no_network (__main__.TestReleaseLookup.test_pinned_needs_no_network) ... ok
test_track_uses_the_given_minor (__main__.TestReleaseLookup.test_track_uses_the_given_minor) ... ok
test_version_found_in_archive_needs_no_network (__main__.TestReleaseLookup.test_version_found_in_archive_needs_no_network) ... ok
test_version_searches_older_releases (__main__.TestReleaseLookup.test_version_searches_older_releases) ... ok
test_last_version_of_a_line_takes_its_alias (__main__.TestRemove.test_last_version_of_a_line_takes_its_alias) ... ok
test_refusals (__main__.TestRemove.test_refusals) ... ok
test_refuses_a_line_version_while_others_remain (__main__.TestRemove.test_refuses_a_line_version_while_others_remain) ... ok
test_refuses_the_default (__main__.TestRemove.test_refuses_the_default) ... ok
test_removes_an_unaliased_version (__main__.TestRemove.test_removes_an_unaliased_version) ... ok
test_claude_directory_is_not_tracked (__main__.TestRepositoryTracksNothingIgnored.test_claude_directory_is_not_tracked) ... skipped 'needs git and a git checkout'
test_no_tracked_file_matches_gitignore (__main__.TestRepositoryTracksNothingIgnored.test_no_tracked_file_matches_gitignore) ... skipped 'needs git and a git checkout'
test_publish_release_checks_before_building (__main__.TestRepositoryTracksNothingIgnored.test_publish_release_checks_before_building) ... skipped 'needs git and a git checkout'
test_root_claude_md_is_tracked (__main__.TestRepositoryTracksNothingIgnored.test_root_claude_md_is_tracked) ... skipped 'needs git and a git checkout'
test_a_scratch_home_inside_the_real_home_is_allowed (__main__.TestSandbox.test_a_scratch_home_inside_the_real_home_is_allowed)
On Windows the temporary directory, %LOCALAPPDATA%\Temp, is inside ... ok
test_inactive_outside_sandbox_mode (__main__.TestSandbox.test_inactive_outside_sandbox_mode) ... ok
test_one_stray_variable_is_enough (__main__.TestSandbox.test_one_stray_variable_is_enough) ... ok
test_protected_locations_on_this_platform (__main__.TestSandbox.test_protected_locations_on_this_platform) ... ok
test_refuses_missing_variables (__main__.TestSandbox.test_refuses_missing_variables) ... ok
test_refuses_the_real_locations (__main__.TestSandbox.test_refuses_the_real_locations) ... ok
test_symlink_into_a_real_location_is_refused (__main__.TestSandbox.test_symlink_into_a_real_location_is_refused) ... skipped "cannot create symbolic links here: [WinError 1314] A required privilege is not held by the client: 'C:\\\\Users\\\\initial\\\\AppData\\\\Local\\\\Temp\\\\manage-python-test-k6edibef\\\\realhome\\\\.config\\\\python-manager' -> 'C:\\\\Users\\\\initial\\\\AppData\\\\Local\\\\Temp\\\\manage-python-test-k6edibef\\\\looks-like-scratch'"
test_the_stray_log_line_cannot_happen_again (__main__.TestSandbox.test_the_stray_log_line_cannot_happen_again)
A smoke run of a failing --switch once wrote a log line into the ... ok
test_this_module_runs_outside_the_real_locations (__main__.TestSandbox.test_this_module_runs_outside_the_real_locations) ... ok
test_windows_real_locations (__main__.TestSandbox.test_windows_real_locations) ... ok
test_windows_registry_is_never_touched_in_sandbox_mode (__main__.TestSandbox.test_windows_registry_is_never_touched_in_sandbox_mode) ... ok
test_write_primitives_refuse_the_real_locations (__main__.TestSandbox.test_write_primitives_refuse_the_real_locations) ... ok
test_key_order (__main__.TestSelfPointer.test_key_order) ... ok
test_manager_alias_can_be_renamed_but_not_taken (__main__.TestSelfPointer.test_manager_alias_can_be_renamed_but_not_taken) ... ok
test_self_keys_round_trip_in_every_format (__main__.TestSelfPointer.test_self_keys_round_trip_in_every_format) ... ok
test_self_version_must_be_a_version (__main__.TestSelfPointer.test_self_version_must_be_a_version) ... ok
test_switch_never_changes_the_manager_version (__main__.TestSelfPointer.test_switch_never_changes_the_manager_version) ... ok
test_archived_only_line_is_shown_without_aliases (__main__.TestStatus.test_archived_only_line_is_shown_without_aliases) ... ok
test_cli_status_reads_the_filesystem (__main__.TestStatus.test_cli_status_reads_the_filesystem) ... ok
test_cli_status_reports_a_broken_pointer (__main__.TestStatus.test_cli_status_reports_a_broken_pointer) ... ok
test_empty (__main__.TestStatus.test_empty) ... ok
test_ignores_non_version_entries (__main__.TestStatus.test_ignores_non_version_entries) ... ok
test_installed_but_no_pointer (__main__.TestStatus.test_installed_but_no_pointer) ... ok
test_matches_proposal_example (__main__.TestStatus.test_matches_proposal_example) ... ok
test_python_moves_with_a_switch_across_lines (__main__.TestStatus.test_python_moves_with_a_switch_across_lines) ... ok
test_renamed_alias_appears_under_new_name (__main__.TestStatus.test_renamed_alias_appears_under_new_name) ... ok
test_several_installed_versions_newest_first (__main__.TestStatus.test_several_installed_versions_newest_first) ... ok
test_warns_about_missing_alias_files (__main__.TestStatus.test_warns_about_missing_alias_files) ... ok
test_warns_when_pointer_names_missing_runtime (__main__.TestStatus.test_warns_when_pointer_names_missing_runtime) ... ok
test_before_any_install (__main__.TestStatusManagerLine.test_before_any_install) ... ok
test_first_line_names_the_manager_and_its_version (__main__.TestStatusManagerLine.test_first_line_names_the_manager_and_its_version) ... ok
test_renamed_manager (__main__.TestStatusManagerLine.test_renamed_manager) ... ok
test_keeps_renamed_aliases (__main__.TestSwitch.test_keeps_renamed_aliases) ... ok
test_refusals (__main__.TestSwitch.test_refusals) ... ok
test_restores_a_missing_alias (__main__.TestSwitch.test_restores_a_missing_alias) ... ok
test_switch_across_lines_moves_python (__main__.TestSwitch.test_switch_across_lines_moves_python) ... ok
test_switch_within_a_line (__main__.TestSwitch.test_switch_within_a_line) ... ok
test_common_cases_from_proposal (__main__.TestTriple.test_common_cases_from_proposal) ... ok
test_detect_libc (__main__.TestTriple.test_detect_libc) ... ok
test_detect_triple_wires_probes (__main__.TestTriple.test_detect_triple_wires_probes) ... ok
test_elf_interpreter_64_and_32_bit (__main__.TestTriple.test_elf_interpreter_64_and_32_bit) ... ok
test_elf_interpreter_on_this_host (__main__.TestTriple.test_elf_interpreter_on_this_host) ... skipped "reads this host's /bin/sh"
test_never_selects_x86_64_variants (__main__.TestTriple.test_never_selects_x86_64_variants) ... ok
test_other_published_linux_and_windows_builds (__main__.TestTriple.test_other_published_linux_and_windows_builds) ... ok
test_rosetta_probe (__main__.TestTriple.test_rosetta_probe) ... ok
test_rosetta_selects_apple_silicon (__main__.TestTriple.test_rosetta_selects_apple_silicon) ... ok
test_translated_flag_ignored_off_macos (__main__.TestTriple.test_translated_flag_ignored_off_macos) ... ok
test_unsupported_platforms_fail_clearly (__main__.TestTriple.test_unsupported_platforms_fail_clearly) ... ok
test_already_present_in_any_spelling (__main__.TestWindowsPath.test_already_present_in_any_spelling) ... ok
test_expand_windows_vars (__main__.TestWindowsPath.test_expand_windows_vars) ... ok
test_missing_path_is_created_expandable (__main__.TestWindowsPath.test_missing_path_is_created_expandable) ... ok
test_prepends_when_absent (__main__.TestWindowsPath.test_prepends_when_absent) ... ok
test_present_means_no_write_and_no_broadcast (__main__.TestWindowsPath.test_present_means_no_write_and_no_broadcast) ... ok
test_reg_sz_gets_the_expanded_path (__main__.TestWindowsPath.test_reg_sz_gets_the_expanded_path) ... ok
test_registry_write_keeps_the_value_type (__main__.TestWindowsPath.test_registry_write_keeps_the_value_type) ... ok
test_similar_entries_are_not_mistaken_for_it (__main__.TestWindowsPath.test_similar_entries_are_not_mistaken_for_it) ... ok
test_unexpected_type_is_refused_and_logged (__main__.TestWindowsPath.test_unexpected_type_is_refused_and_logged) ... ok
test_already_present_prints_logs_and_backs_up_nothing (__main__.TestWindowsPathChangeIsVisible.test_already_present_prints_logs_and_backs_up_nothing) ... ok
test_announcement (__main__.TestWindowsPathChangeIsVisible.test_announcement) ... ok
test_backup_is_written_before_the_registry (__main__.TestWindowsPathChangeIsVisible.test_backup_is_written_before_the_registry) ... ok
test_backup_keeps_the_previous_value_and_type (__main__.TestWindowsPathChangeIsVisible.test_backup_keeps_the_previous_value_and_type) ... ok
test_backup_of_a_missing_value (__main__.TestWindowsPathChangeIsVisible.test_backup_of_a_missing_value) ... ok
test_failed_broadcast_still_counts_as_a_change (__main__.TestWindowsPathChangeIsVisible.test_failed_broadcast_still_counts_as_a_change) ... ok
test_failed_write_is_logged_and_does_not_raise (__main__.TestWindowsPathChangeIsVisible.test_failed_write_is_logged_and_does_not_raise) ... ok
test_log_line (__main__.TestWindowsPathChangeIsVisible.test_log_line) ... ok
test_messages_go_through_gettext (__main__.TestWindowsPathChangeIsVisible.test_messages_go_through_gettext) ... ok
test_sandbox_mode_writes_nothing (__main__.TestWindowsPathChangeIsVisible.test_sandbox_mode_writes_nothing) ... ok
test_generic_alias_refusal_names_python (__main__.TestWriteAlias.test_generic_alias_refusal_names_python) ... ok
test_overwrites_its_own_alias (__main__.TestWriteAlias.test_overwrites_its_own_alias) ... ok
test_refuses_bad_names (__main__.TestWriteAlias.test_refuses_bad_names) ... ok
test_refuses_foreign_file_and_suggests_alias (__main__.TestWriteAlias.test_refuses_foreign_file_and_suggests_alias) ... ok
test_windows_alias_is_one_cmd_file_with_crlf (__main__.TestWriteAlias.test_windows_alias_is_one_cmd_file_with_crlf) ... ok
test_windows_foreign_cmd_blocks_the_alias (__main__.TestWriteAlias.test_windows_foreign_cmd_blocks_the_alias) ... ok
test_writes_executable_alias (__main__.TestWriteAlias.test_writes_executable_alias) ... skipped 'exercises POSIX modes and /bin/sh'

----------------------------------------------------------------------
Ran 235 tests in 22.156s

OK (skipped=19)

```

