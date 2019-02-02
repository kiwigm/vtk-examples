#include <vtkActor.h>
#include <vtkCallbackCommand.h>
#include <vtkCommand.h>
#include <vtkInteractorStyleTrackballCamera.h>
#include <vtkMath.h>
#include <vtkNamedColors.h>
#include <vtkNew.h>
#include <vtkOBBTree.h>
#include <vtkPointSource.h>
#include <vtkPolyData.h>
#include <vtkPolyDataMapper.h>
#include <vtkProperty.h>
#include <vtkProperty2D.h>
#include <vtkRenderWindow.h>
#include <vtkRenderWindowInteractor.h>
#include <vtkRenderer.h>
#include <vtkSliderRepresentation2D.h>
#include <vtkSliderWidget.h>
#include <vtkSmartPointer.h>
#include <vtkSphereSource.h>
#include <vtkTextProperty.h>
#include <vtkWidgetEvent.h>
#include <vtkWidgetEventTranslator.h>

namespace {
class vtkSliderCallback : public vtkCommand {
public:
  static vtkSliderCallback *New() { return new vtkSliderCallback; }

  vtkSliderCallback() : OBBTree(0), Level(0), PolyData(0), Renderer(0) {}

  virtual void Execute(vtkObject *caller, unsigned long, void *) {
    vtkSliderWidget *sliderWidget = reinterpret_cast<vtkSliderWidget *>(caller);
    this->Level = vtkMath::Round(static_cast<vtkSliderRepresentation *>(
                                     sliderWidget->GetRepresentation())
                                     ->GetValue());
    this->OBBTree->GenerateRepresentation(this->Level, this->PolyData);
    this->Renderer->Render();
  }

  vtkOBBTree *OBBTree;
  int Level;
  vtkPolyData *PolyData;
  vtkRenderer *Renderer;
};
} // namespace

int main(int, char *[]) {
  vtkNew<vtkNamedColors> colors;

  // Create a point cloud - OBBTree currently requires cells
  /*
  vtkSmartPointer<vtkPointSource> pointSource =
    vtkSmartPointer<vtkPointSource>::New();
  pointSource->SetRadius(4);
  pointSource->SetNumberOfPoints(1000);
  pointSource->Update();
  */

  vtkSmartPointer<vtkSphereSource> inputSource =
      vtkSmartPointer<vtkSphereSource>::New();
  inputSource->SetPhiResolution(10);
  inputSource->SetThetaResolution(10);
  inputSource->Update();

  vtkSmartPointer<vtkPolyDataMapper> pointsMapper =
      vtkSmartPointer<vtkPolyDataMapper>::New();
  pointsMapper->SetInputConnection(inputSource->GetOutputPort());

  vtkSmartPointer<vtkActor> pointsActor = vtkSmartPointer<vtkActor>::New();
  pointsActor->SetMapper(pointsMapper);
  pointsActor->GetProperty()->SetInterpolationToFlat();
  pointsActor->GetProperty()->SetColor(colors->GetColor4d("Yellow").GetData());

  // Create the tree
  vtkSmartPointer<vtkOBBTree> obbTree = vtkSmartPointer<vtkOBBTree>::New();
  obbTree->SetDataSet(inputSource->GetOutput());
  obbTree->BuildLocator();

  // Initialize the representation
  vtkSmartPointer<vtkPolyData> polydata = vtkSmartPointer<vtkPolyData>::New();
  obbTree->GenerateRepresentation(0, polydata);

  vtkSmartPointer<vtkPolyDataMapper> obbtreeMapper =
      vtkSmartPointer<vtkPolyDataMapper>::New();
  obbtreeMapper->SetInputData(polydata);

  vtkSmartPointer<vtkActor> obbtreeActor = vtkSmartPointer<vtkActor>::New();
  obbtreeActor->SetMapper(obbtreeMapper);
  obbtreeActor->GetProperty()->SetInterpolationToFlat();
  obbtreeActor->GetProperty()->SetRepresentationToWireframe();
  obbtreeActor->GetProperty()->SetColor(
      colors->GetColor4d("SpringGreen").GetData());

  // A renderer and render window
  vtkSmartPointer<vtkRenderer> renderer = vtkSmartPointer<vtkRenderer>::New();
  vtkSmartPointer<vtkRenderWindow> renderWindow =
      vtkSmartPointer<vtkRenderWindow>::New();
  renderWindow->AddRenderer(renderer);

  // An interactor
  vtkSmartPointer<vtkRenderWindowInteractor> renderWindowInteractor =
      vtkSmartPointer<vtkRenderWindowInteractor>::New();
  renderWindowInteractor->SetRenderWindow(renderWindow);

  // Add the actors to the scene
  renderer->AddActor(pointsActor);
  renderer->AddActor(obbtreeActor);
  renderer->SetBackground(colors->GetColor3d("MidnightBlue").GetData());

  // Render an image (lights and cameras are created automatically)
  renderWindow->SetWindowName("VisualizeOBBTree");
  renderWindow->SetSize(600, 600);
  renderWindow->Render();

  vtkSmartPointer<vtkSliderRepresentation2D> sliderRep =
      vtkSmartPointer<vtkSliderRepresentation2D>::New();
  sliderRep->SetMinimumValue(0);
  sliderRep->SetMaximumValue(obbTree->GetLevel());
  sliderRep->SetValue(0);
  sliderRep->SetTitleText("Level");
  sliderRep->GetPoint1Coordinate()->SetCoordinateSystemToNormalizedDisplay();
  sliderRep->GetPoint1Coordinate()->SetValue(.2, .2);
  sliderRep->GetPoint2Coordinate()->SetCoordinateSystemToNormalizedDisplay();
  sliderRep->GetPoint2Coordinate()->SetValue(.8, .2);
  sliderRep->SetSliderLength(0.075);
  sliderRep->SetSliderWidth(0.05);
  sliderRep->SetEndCapLength(0.05);
  sliderRep->GetTitleProperty()->SetColor(
      colors->GetColor3d("Beige").GetData());
  sliderRep->GetCapProperty()->SetColor(
      colors->GetColor3d("MistyRose").GetData());
  sliderRep->GetSliderProperty()->SetColor(
      colors->GetColor3d("LightBlue").GetData());
  sliderRep->GetSelectedProperty()->SetColor(
      colors->GetColor3d("Violet").GetData());

  vtkSmartPointer<vtkSliderWidget> sliderWidget =
      vtkSmartPointer<vtkSliderWidget>::New();
  sliderWidget->SetInteractor(renderWindowInteractor);
  sliderWidget->SetRepresentation(sliderRep);
  sliderWidget->SetAnimationModeToAnimate();
  sliderWidget->EnabledOn();

  vtkSmartPointer<vtkSliderCallback> callback =
      vtkSmartPointer<vtkSliderCallback>::New();
  callback->OBBTree = obbTree;
  callback->PolyData = polydata;
  callback->Renderer = renderer;

  sliderWidget->AddObserver(vtkCommand::InteractionEvent, callback);

  renderWindowInteractor->Initialize();
  renderWindow->Render();

  renderWindowInteractor->Start();

  return EXIT_SUCCESS;
}
