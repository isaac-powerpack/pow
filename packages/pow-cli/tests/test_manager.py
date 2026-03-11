import pytest
from pathlib import Path
from pow_cli.core.manager import Manager

class TestManager:
    @pytest.fixture(autouse=True)
    def mock_manager_environment(self, mocker):
        """Mock the environment paths for Manager."""
        self.mock_get_name = mocker.patch("pow_cli.core.manager.get_global_dir_name", return_value=".pow")
        self.mock_home = mocker.patch("pathlib.Path.home", return_value=Path("/home/user"))

    def test_create_global_folder_new(self, mocker):
        manager = Manager()
        
        # Mock existence: global doesn't exist
        mocker.patch.object(Path, "exists", return_value=False)
        mock_mkdir = mocker.patch.object(Path, "mkdir")
        
        init_data = manager.create_global_folder()
        
        # Should call mkdir for global path and subfolders
        # global_path.mkdir + 4 subfolder.mkdir
        assert mock_mkdir.call_count == 5
        assert init_data["global_existed"] is False
        assert all(r["status"] == "Created" for r in init_data["results"])

    def test_create_global_folder_exists_skips_subfolders(self, mocker):
        manager = Manager()
        
        # Mock existence: global EXISTS, subfolders DON'T
        def side_effect(path_obj):
            if path_obj == manager.global_path:
                return True
            return False

        mocker.patch.object(Path, "exists", side_effect=side_effect, autospec=True)
        mock_mkdir = mocker.patch.object(Path, "mkdir")
        
        init_data = manager.create_global_folder()
        
        # Should NOT call mkdir at all if global exists
        mock_mkdir.assert_not_called()
        assert init_data["global_existed"] is True
        assert all(r["status"] == "Skipped" for r in init_data["results"])

    def test_create_global_folder_exists_some_subfolders(self, mocker):
        manager = Manager()
        
        # Mock existence: global EXISTS, some subfolders EXIST
        def side_effect(path_obj):
            if path_obj == manager.global_path:
                return True
            if "isaacsim" in str(path_obj):
                return True
            return False

        mocker.patch.object(Path, "exists", side_effect=side_effect, autospec=True)
        mock_mkdir = mocker.patch.object(Path, "mkdir")
        
        init_data = manager.create_global_folder()
        
        mock_mkdir.assert_not_called()
        assert init_data["global_existed"] is True
        
        isaacsim_res = next(r for r in init_data["results"] if "isaacsim" in r["path"])
        modules_res = next(r for r in init_data["results"] if "modules" in r["path"])
        
        assert isaacsim_res["status"] == "Existed"
        assert modules_res["status"] == "Skipped"
