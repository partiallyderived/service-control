import json
import os

import enough

from servicecontrol.tools.data import DataService


def test_data() -> None:
    # Run simple tests to make sure DataService functions correctly.
    with enough.temp_file_path() as path:
        config = {'path': path}
        service = DataService(config)
        service.data['my_data'] = [1, 'asdf', True]
        service.save()
        with open(path) as f:
            assert json.load(f) == {'my_data': [1, 'asdf', True]}
        service2 = DataService(config)

        # Test that start loads existing data.
        service2.start()
        assert service.data == {'my_data': [1, 'asdf', True]}

        # Test that purge removes the data file.
        service.purge()
        assert not os.path.isfile(path)

        # Test that stop saves the data file.
        service.stop()
        assert os.path.isfile(path)
