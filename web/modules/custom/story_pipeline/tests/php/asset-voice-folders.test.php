<?php
// Standalone storage regression checks; no Drupal database or bootstrap required.
namespace Drupal\Core\Config { interface ConfigFactoryInterface {} }
namespace Drupal\node { interface NodeInterface {} }
namespace Drupal\taxonomy { interface TermInterface {} }
namespace {
  require __DIR__ . '/../../src/Service/StoryPipelineAssetStorage.php';
  class VoiceTerm implements \Drupal\taxonomy\TermInterface {
    public function __construct(private string $name) {}
    public function label(): string { return $this->name; }
  }
  class VoiceField {
    public function __construct(public $entity) {}
    public function isEmpty(): bool { return $this->entity === NULL; }
  }
  class VoiceNode implements \Drupal\node\NodeInterface {
    public function __construct(public string $title, public ?string $voice) {}
    public function id(): int { return 203; }
    public function getTitle(): string { return $this->title; }
    public function bundle(): string { return 'story'; }
    public function hasField($name): bool { return TRUE; }
    public function get($name): VoiceField {
      return new VoiceField($name === 'field_story_type' ? new VoiceTerm('General') : ($this->voice ? new VoiceTerm($this->voice) : NULL));
    }
  }
  class VoiceConfig implements \Drupal\Core\Config\ConfigFactoryInterface {
    public function __construct(public string $root) {}
    public function get($name) { return new class($this->root) {
      public function __construct(private string $root) {}
      public function get($name) { return $this->root; }
    }; }
  }
  function check($condition): void { if (!$condition) { throw new \RuntimeException('Storage regression failed'); } }
  $root = sys_get_temp_dir() . '/voice-folder-test-' . bin2hex(random_bytes(6));
  mkdir($root);
  $root = realpath($root);
  $storage = new \Drupal\story_pipeline\Service\StoryPipelineAssetStorage(new VoiceConfig($root));
  $node = new VoiceNode('New Story', 'Bindass Gupshup');
  check($storage->folderName($node) === '203-new-story--voice-bindass-gupshup');
  check($storage->resolveStoryDir($node) === $root . '/general/203-new-story--voice-bindass-gupshup');
  mkdir($root . '/general/203-new-story', 0775, TRUE);
  check($storage->resolveStoryDir($node) === $root . '/general/203-new-story');
  mkdir($root . '/general/203-new-story/meta');
  file_put_contents($root . '/general/203-new-story/meta/drupal-node-id.txt', '203');
  $node->title = 'Changed Title'; $node->voice = 'God';
  check($storage->resolveStoryDir($node) === $root . '/general/203-new-story');
  $node->voice = NULL;
  check($storage->folderName($node) === '203-changed-title');
  unlink($root . '/general/203-new-story/meta/drupal-node-id.txt');
  rmdir($root . '/general/203-new-story/meta'); rmdir($root . '/general/203-new-story');
  rmdir($root . '/general'); rmdir($root);
  echo "PHP voice folder checks passed\n";
}
